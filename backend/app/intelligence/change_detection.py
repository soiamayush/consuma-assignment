"""Detect meaningful changes between scrape runs and materialize them as `Signal` rows.

Signals are upserted via a stable `dedupe_key` so re-running ingestion is idempotent.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BlogPost, Competitor, Product, ProductSnapshot, Signal
from ..time_utils import utc_now
from . import themes as themes_mod
from .scoring import score_signal

logger = logging.getLogger(__name__)

# Threshold to consider a price change meaningful (avoids cents-level noise).
PRICE_CHANGE_MIN_PCT = 0.03  # 3%
CATALOG_SURGE_THRESHOLD = 5  # new products in a single run


@dataclass
class ChangeStats:
    signals_created: int = 0


def _hash(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def upsert_signal(
    db: Session,
    *,
    competitor: Competitor,
    kind: str,
    entity_type: str,
    entity_id: int | None,
    title: str,
    description: str | None,
    delta: dict[str, Any],
    source_text: str | None = None,
    created_at: datetime | None = None,
) -> Signal | None:
    created_at = created_at or utc_now()
    dedupe_key = _hash(competitor.id, kind, entity_type, entity_id, delta.get("dedupe_tag", ""))

    existing = db.scalar(select(Signal).where(Signal.dedupe_key == dedupe_key))
    if existing:
        return None

    theme_list = themes_mod.classify_many([title, description, source_text])
    score, breakdown = score_signal(
        kind=kind,
        created_at=created_at,
        delta=delta,
        themes=theme_list,
        brand_weight=competitor.brand_weight,
    )
    delta_full = {**delta, "score_breakdown": breakdown}
    sig = Signal(
        competitor_id=competitor.id,
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        description=description,
        delta=delta_full,
        themes=theme_list,
        importance=score,
        dedupe_key=dedupe_key,
        created_at=created_at,
    )
    db.add(sig)
    return sig


def detect_product_changes(
    db: Session,
    competitor: Competitor,
    product: Product,
    previous: ProductSnapshot | None,
    current: ProductSnapshot,
    stats: ChangeStats,
) -> None:
    """Compare two snapshots and emit signals for meaningful changes.

    `previous is None` means we just created the product in this run -> LAUNCH.
    """
    if previous is None:
        sig = upsert_signal(
            db,
            competitor=competitor,
            kind="PRODUCT_LAUNCH",
            entity_type="product",
            entity_id=product.id,
            title=f"New product: {product.title}",
            description=f"{competitor.name} added a new product to their catalog.",
            delta={
                "dedupe_tag": f"launch:{product.external_id}",
                "price_min": current.price_min,
                "price_max": current.price_max,
                "currency": current.currency,
                "tags": product.tags,
            },
            source_text=" ".join([product.title] + (product.tags or []) + [product.product_type or ""]),
        )
        if sig:
            stats.signals_created += 1
        return

    # Price change
    if previous.price_min is not None and current.price_min is not None and previous.price_min > 0:
        pct = (current.price_min - previous.price_min) / previous.price_min
        if abs(pct) >= PRICE_CHANGE_MIN_PCT:
            kind = "PRICE_DROP" if pct < 0 else "PRICE_INCREASE"
            direction = "dropped" if pct < 0 else "increased"
            sig = upsert_signal(
                db,
                competitor=competitor,
                kind=kind,
                entity_type="product",
                entity_id=product.id,
                title=f"Price {direction} on {product.title}",
                description=(
                    f"Price went from {previous.price_min:.2f} to {current.price_min:.2f} "
                    f"({pct*100:+.1f}%)."
                ),
                delta={
                    "dedupe_tag": f"price:{product.external_id}:{previous.captured_at.isoformat()}",
                    "old_price": previous.price_min,
                    "new_price": current.price_min,
                    "pct_change": pct,
                    "currency": current.currency,
                },
                source_text=product.title,
            )
            if sig:
                stats.signals_created += 1

    # Availability change
    if previous.available and not current.available:
        sig = upsert_signal(
            db,
            competitor=competitor,
            kind="OUT_OF_STOCK",
            entity_type="product",
            entity_id=product.id,
            title=f"Sold out: {product.title}",
            description="All variants currently unavailable.",
            delta={"dedupe_tag": f"oos:{product.external_id}:{current.captured_at.isoformat()}"},
            source_text=product.title,
        )
        if sig:
            stats.signals_created += 1
    elif (not previous.available) and current.available:
        sig = upsert_signal(
            db,
            competitor=competitor,
            kind="BACK_IN_STOCK",
            entity_type="product",
            entity_id=product.id,
            title=f"Back in stock: {product.title}",
            description="Product became available again.",
            delta={"dedupe_tag": f"bis:{product.external_id}:{current.captured_at.isoformat()}"},
            source_text=product.title,
        )
        if sig:
            stats.signals_created += 1


def detect_catalog_surge(
    db: Session,
    competitor: Competitor,
    new_products: list[Product],
    stats: ChangeStats,
) -> None:
    if len(new_products) < CATALOG_SURGE_THRESHOLD:
        return
    titles = ", ".join(p.title for p in new_products[:5])
    sig = upsert_signal(
        db,
        competitor=competitor,
        kind="CATALOG_SURGE",
        entity_type="competitor",
        entity_id=competitor.id,
        title=f"{competitor.name} added {len(new_products)} new products",
        description=f"Recent additions include: {titles}…",
        delta={
            "dedupe_tag": f"surge:{competitor.id}:{utc_now().date().isoformat()}",
            "new_products": len(new_products),
            "sample_titles": [p.title for p in new_products[:10]],
        },
        source_text=titles,
    )
    if sig:
        stats.signals_created += 1


def detect_blog_post(
    db: Session,
    competitor: Competitor,
    post: BlogPost,
    is_new: bool,
    stats: ChangeStats,
) -> None:
    if not is_new:
        return
    # Skip very old posts on first ingest to avoid flooding the feed.
    if post.published_at and post.published_at < utc_now() - timedelta(days=120):
        return
    sig = upsert_signal(
        db,
        competitor=competitor,
        kind="BLOG_POST",
        entity_type="blog",
        entity_id=post.id,
        title=post.title,
        description=post.summary,
        delta={"dedupe_tag": f"blog:{post.external_id}", "url": post.url},
        source_text=" ".join(filter(None, [post.title, post.summary])),
        created_at=post.published_at or post.first_seen_at,
    )
    if sig:
        stats.signals_created += 1
