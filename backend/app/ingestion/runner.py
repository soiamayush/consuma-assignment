"""Ingestion runner: orchestrates a run for one Source.

Responsibilities:
  1. Build the concrete scraper via the registry.
  2. Pull items (paginated, retried at HTTP layer).
  3. Validate + dedupe (by competitor_id + external_id).
  4. For products: compare the new snapshot to the last stored snapshot,
     write a new snapshot if the content hash changed, and feed
     `change_detection` to create Signal rows.
  5. Track stats on the IngestionRun row for observability.

This module is invoked either from the CLI (`python -m app.ingestion.runner`)
or from the API (`POST /api/ingest/run`).
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..intelligence import change_detection as cd
from ..models import (
    BlogPost,
    Competitor,
    IngestionRun,
    Product,
    ProductSnapshot,
    SocialMention,
    Source,
)
from ..scrapers.base import FetchContext, RawBlogPost, RawProduct, RawSocialMention, SourceError
from ..scrapers.registry import build_source
from ..time_utils import as_naive_utc, utc_now

logger = logging.getLogger(__name__)


def _is_hybrid_fallback_source(src: Source) -> bool:
    return bool((src.config or {}).get("only_if_empty_fallback"))


# Primary sources that populate the product catalog (excludes blogs / fixture rows).
_CATALOG_PRODUCT_SOURCE_KINDS = frozenset(
    {
        "shopify_products",
        "myglamm_internal_api",
        "browser_listing",
        "html_listing",
        "mamaearth_sitemap",
    }
)


def _raw_compare_at(raw: RawProduct) -> tuple[float | None, float | None]:
    r = raw.raw or {}
    lo = r.get("compare_at_min")
    hi = r.get("compare_at_max")
    try:
        lo_f = float(lo) if lo is not None else None
    except (TypeError, ValueError):
        lo_f = None
    try:
        hi_f = float(hi) if hi is not None else None
    except (TypeError, ValueError):
        hi_f = None
    return lo_f, hi_f


def _snapshot_hash(raw: RawProduct) -> str:
    ca_lo, ca_hi = _raw_compare_at(raw)
    parts = [
        raw.title,
        f"{raw.price_min}",
        f"{raw.price_max}",
        f"{ca_lo}",
        f"{ca_hi}",
        raw.currency or "",
        "1" if raw.available else "0",
        str(raw.variants_count),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _valid_product(raw: RawProduct) -> bool:
    if not raw.external_id:
        return False
    if not raw.title or raw.title.strip() == "":
        return False
    return True


def _valid_blog(raw: RawBlogPost) -> bool:
    return bool(raw.external_id and raw.title and raw.url)


def _valid_social(raw: RawSocialMention) -> bool:
    return bool(raw.external_id and raw.platform and raw.title and raw.url)


def _ctx() -> FetchContext:
    s = get_settings()
    return FetchContext(
        user_agent=s.scrape_user_agent,
        timeout=s.scrape_timeout,
        max_pages=s.scrape_max_pages,
    )


def run_source(db: Session, source: Source) -> IngestionRun:
    run = IngestionRun(source_id=source.id, started_at=utc_now(), status="running")
    db.add(run)
    db.flush()  # get id

    competitor = source.competitor
    stats = cd.ChangeStats()

    try:
        scraper = build_source(source.kind, source.url, source.config or {})
        ctx = _ctx()

        products_seen = 0
        products_new = 0
        products_changed = 0
        blog_new = 0

        newly_created_products: list[Product] = []

        # ---- Products ------------------------------------------------------
        for raw in scraper.fetch_products(ctx):
            if not _valid_product(raw):
                continue
            products_seen += 1
            result = _upsert_product(db, competitor, raw, stats, newly_created_products)
            if result == "new":
                products_new += 1
            elif result == "changed":
                products_changed += 1

        # Catalog-surge signal if many new products arrived in a single run.
        if newly_created_products:
            cd.detect_catalog_surge(db, competitor, newly_created_products, stats)

        # ---- Blog posts ----------------------------------------------------
        for rawb in scraper.fetch_blog_posts(ctx):
            if not _valid_blog(rawb):
                continue
            products_seen += 1
            is_new, bp = _upsert_blog(db, competitor, rawb)
            if is_new:
                blog_new += 1
                cd.detect_blog_post(db, competitor, bp, True, stats)

        # ---- Social mentions (YouTube / Reddit / Google News) ---------------
        social_new = 0
        social_changed = 0
        for raws in scraper.fetch_social_mentions(ctx):
            if not _valid_social(raws):
                continue
            products_seen += 1
            outcome = _upsert_social_mention(db, competitor, raws)
            if outcome == "new":
                social_new += 1
            elif outcome == "changed":
                social_changed += 1

        run.items_seen = products_seen
        run.items_new = products_new + blog_new + social_new
        run.items_changed = products_changed + social_changed
        run.signals_created = stats.signals_created
        run.status = "ok"
    except SourceError as exc:
        run.status = "error"
        run.error = str(exc)
        logger.exception("source error kind=%s url=%s", source.kind, source.url)
    except Exception as exc:  # never let one source break the whole run
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
        logger.exception("unexpected ingestion error")
    finally:
        run.finished_at = utc_now()
        source.last_run_at = run.finished_at
        source.last_status = run.status
        db.add(source)

    return run


def _upsert_product(
    db: Session,
    competitor: Competitor,
    raw: RawProduct,
    stats: cd.ChangeStats,
    newly_created: list[Product],
) -> str:
    """Returns 'new', 'changed', or 'unchanged'."""
    existing = db.scalar(
        select(Product).where(
            Product.competitor_id == competitor.id,
            Product.external_id == raw.external_id,
        )
    )
    now = utc_now()
    new_hash = _snapshot_hash(raw)

    if existing is None:
        ca_lo, ca_hi = _raw_compare_at(raw)
        product = Product(
            competitor_id=competitor.id,
            external_id=raw.external_id,
            handle=raw.handle,
            title=raw.title,
            product_type=raw.product_type,
            vendor=raw.vendor,
            url=raw.url,
            image_url=raw.image_url,
            tags=raw.tags,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
        )
        db.add(product)
        db.flush()
        snap = ProductSnapshot(
            product_id=product.id,
            captured_at=now,
            title=raw.title,
            price_min=raw.price_min,
            price_max=raw.price_max,
            compare_at_min=ca_lo,
            compare_at_max=ca_hi,
            currency=raw.currency,
            available=raw.available,
            variants_count=raw.variants_count,
            content_hash=new_hash,
        )
        db.add(snap)
        db.flush()
        cd.detect_product_changes(db, competitor, product, previous=None, current=snap, stats=stats)
        newly_created.append(product)
        return "new"

    # Existing: update last_seen, then decide whether to record a new snapshot.
    existing.last_seen_at = now
    existing.title = raw.title
    existing.image_url = raw.image_url or existing.image_url
    existing.url = raw.url or existing.url
    existing.tags = raw.tags or existing.tags
    existing.is_active = True

    latest = db.scalar(
        select(ProductSnapshot)
        .where(ProductSnapshot.product_id == existing.id)
        .order_by(ProductSnapshot.captured_at.desc())
        .limit(1)
    )

    if latest and latest.content_hash == new_hash:
        return "unchanged"

    ca_lo, ca_hi = _raw_compare_at(raw)
    snap = ProductSnapshot(
        product_id=existing.id,
        captured_at=now,
        title=raw.title,
        price_min=raw.price_min,
        price_max=raw.price_max,
        compare_at_min=ca_lo,
        compare_at_max=ca_hi,
        currency=raw.currency,
        available=raw.available,
        variants_count=raw.variants_count,
        content_hash=new_hash,
    )
    db.add(snap)
    db.flush()
    cd.detect_product_changes(db, competitor, existing, previous=latest, current=snap, stats=stats)
    return "changed"


def _upsert_social_mention(
    db: Session, competitor: Competitor, raw: RawSocialMention
) -> str:
    """Upsert one social mention. Returns 'new' / 'changed' / 'unchanged'."""
    existing = db.scalar(
        select(SocialMention).where(
            SocialMention.competitor_id == competitor.id,
            SocialMention.platform == raw.platform,
            SocialMention.external_id == raw.external_id,
        )
    )
    if existing is None:
        sm = SocialMention(
            competitor_id=competitor.id,
            platform=raw.platform,
            external_id=raw.external_id,
            url=raw.url,
            title=raw.title[:500],
            summary=raw.summary,
            author=raw.author,
            author_handle=raw.author_handle,
            author_url=raw.author_url,
            thumbnail_url=raw.thumbnail_url,
            metric_views=raw.metric_views,
            metric_score=raw.metric_score,
            metric_comments=raw.metric_comments,
            published_at=as_naive_utc(raw.published_at),
            raw=raw.raw or {},
        )
        db.add(sm)
        db.flush()
        return "new"

    changed = False
    for field_name, new_val in (
        ("title", raw.title[:500]),
        ("summary", raw.summary),
        ("metric_views", raw.metric_views),
        ("metric_score", raw.metric_score),
        ("metric_comments", raw.metric_comments),
        ("thumbnail_url", raw.thumbnail_url),
    ):
        if getattr(existing, field_name) != new_val and new_val is not None:
            setattr(existing, field_name, new_val)
            changed = True
    return "changed" if changed else "unchanged"


def _upsert_blog(db: Session, competitor: Competitor, raw: RawBlogPost) -> tuple[bool, BlogPost]:
    existing = db.scalar(
        select(BlogPost).where(
            BlogPost.competitor_id == competitor.id,
            BlogPost.external_id == raw.external_id,
        )
    )
    chash = hashlib.sha1(f"{raw.title}|{raw.summary or ''}".encode()).hexdigest()
    if existing:
        if existing.content_hash != chash:
            existing.title = raw.title
            existing.summary = raw.summary
            existing.content_hash = chash
        return False, existing
    bp = BlogPost(
        competitor_id=competitor.id,
        external_id=raw.external_id,
        url=raw.url,
        title=raw.title,
        summary=raw.summary,
        published_at=as_naive_utc(raw.published_at),
        content_hash=chash,
    )
    db.add(bp)
    db.flush()
    return True, bp


def run_all(db: Session, competitor_slugs: Iterable[str] | None = None) -> list[IngestionRun]:
    settings = get_settings()
    q = select(Source).where(Source.enabled.is_(True))
    if competitor_slugs:
        slugs = list(competitor_slugs)
        q = q.join(Competitor).where(Competitor.slug.in_(slugs))
    sources = list(db.scalars(q))
    by_comp: dict[int, list[Source]] = defaultdict(list)
    for src in sources:
        by_comp[src.competitor_id].append(src)

    runs: list[IngestionRun] = []
    for comp_id in sorted(by_comp.keys()):
        bloc = by_comp[comp_id]
        primary = sorted((s for s in bloc if not _is_hybrid_fallback_source(s)), key=lambda s: s.id)
        fallback = sorted((s for s in bloc if _is_hybrid_fallback_source(s)), key=lambda s: s.id)
        comp = bloc[0].competitor

        catalog_primary_failed = False
        for src in primary:
            logger.info(
                "ingesting source id=%s kind=%s competitor=%s", src.id, src.kind, src.competitor.slug
            )
            run = run_source(db, src)
            runs.append(run)
            db.commit()
            if src.kind in _CATALOG_PRODUCT_SOURCE_KINDS and run.status == "error":
                catalog_primary_failed = True

        if not fallback:
            continue
        if not settings.hybrid_fixture_fallback:
            logger.info(
                "skip hybrid fixture sources competitor=%s (hybrid_fixture_fallback=false)",
                comp.slug,
            )
            continue

        n = db.scalar(select(func.count(Product.id)).where(Product.competitor_id == comp_id)) or 0
        need_fixture = n == 0 or catalog_primary_failed
        if not need_fixture:
            logger.info(
                "skip hybrid fixture fallback competitor=%s (products=%s, catalog_ok)",
                comp.slug,
                n,
            )
            continue

        reason = (
            "catalog_source_errored"
            if catalog_primary_failed
            else "empty_catalog"
        )
        logger.info(
            "hybrid fixture fallback competitor=%s reason=%s products=%s",
            comp.slug,
            reason,
            n,
        )
        for src in fallback:
            logger.info(
                "ingesting source id=%s kind=%s competitor=%s (fallback)",
                src.id,
                src.kind,
                src.competitor.slug,
            )
            runs.append(run_source(db, src))
            db.commit()

    return runs


# CLI entrypoint -----------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Run competitor ingestion.")
    parser.add_argument("--slugs", nargs="*", help="Limit to these competitor slugs")
    args = parser.parse_args()

    from ..db import init_db, session_scope

    init_db()
    with session_scope() as db:
        runs = run_all(db, competitor_slugs=args.slugs)
        for r in runs:
            print(
                f"[{r.status}] source={r.source_id} seen={r.items_seen} "
                f"new={r.items_new} changed={r.items_changed} signals={r.signals_created} "
                + (f"err={r.error}" if r.error else "")
            )
