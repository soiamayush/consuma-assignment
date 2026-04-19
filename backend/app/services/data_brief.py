"""Build a compact JSON brief of the whole competitive landscape.

We don't do vector RAG — the dataset is small (~few thousand SKUs across a
handful of brands) and analytical questions need *exact* numbers, not nearest
neighbour text. Instead, we pre-pack a structured snapshot per chat turn:

* Anchor + peers (slug, name, weight, SKU/signal counts)
* Price landscape (p25/median/p75, currency, discount intensity)
* Stock pressure, top price moves, anchor white-space
* Category index (top product_types with counts)
* Recent signals (newest N) and recent launches
* Top social mentions (if SocialMention rows exist)

Total payload usually 10–25 KB — comfortably fits Gemini 2.5 Flash and gives
the model enough grounding to answer "where should I focus in serums?" without
reading raw rows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..api.analytics import analytics_overview
from ..models import Competitor, Product, ProductSnapshot, Signal
from ..time_utils import utc_now

try:  # SocialMention is optional in some installs.
    from ..models import SocialMention  # type: ignore
    _HAS_SOCIAL = True
except Exception:  # pragma: no cover - defensive
    SocialMention = None  # type: ignore
    _HAS_SOCIAL = False


def _round(v: Any, n: int = 2) -> Any:
    if isinstance(v, (int, float)):
        return round(float(v), n)
    return v


def build_brief(db: Session, window_days: int = 14) -> dict[str, Any]:
    """Return the whole landscape as a compact JSON-serialisable dict."""
    overview = analytics_overview(window_days=window_days, db=db)

    comps = list(
        db.scalars(
            select(Competitor).order_by(Competitor.is_anchor.desc(), Competitor.brand_weight.desc())
        )
    )

    # ---- Per-brand mini block (counts only — full price/discount lives in landscape).
    brand_blocks: list[dict[str, Any]] = []
    for c in comps:
        n_products = len(list(db.scalars(select(Product.id).where(Product.competitor_id == c.id, Product.is_active.is_(True)))))
        n_signals = len(list(db.scalars(select(Signal.id).where(Signal.competitor_id == c.id))))
        brand_blocks.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "weight": c.brand_weight,
                "website": c.website,
                "product_count": n_products,
                "signal_count": n_signals,
            }
        )

    # ---- Category index (top product_types with brand-level counts).
    cat_total: Counter[str] = Counter()
    cat_by_brand: dict[str, Counter[str]] = defaultdict(Counter)
    products = list(
        db.scalars(
            select(Product)
            .options(selectinload(Product.competitor))
            .where(Product.is_active.is_(True))
        )
    )
    for p in products:
        ct = (p.product_type or "").strip()
        if not ct:
            continue
        cat_total[ct] += 1
        cat_by_brand[ct][p.competitor.slug] += 1

    categories = []
    for ct, total in cat_total.most_common(25):
        per = cat_by_brand[ct].most_common()
        categories.append(
            {
                "category": ct,
                "total_skus": total,
                "by_brand": [{"slug": s, "skus": n} for s, n in per],
            }
        )

    # ---- Recent signals (window) — compact tuple list.
    since = utc_now() - timedelta(days=window_days)
    recent_signals_q = (
        select(Signal)
        .options(selectinload(Signal.competitor))
        .where(Signal.created_at >= since)
        .order_by(Signal.importance.desc(), Signal.created_at.desc())
        .limit(40)
    )
    recent_signals = []
    for s in db.scalars(recent_signals_q):
        delta = s.delta or {}
        recent_signals.append(
            {
                "kind": s.kind,
                "brand": s.competitor.slug if s.competitor else None,
                "title": s.title,
                "importance": _round(s.importance, 2),
                "pct_change": _round(delta.get("pct_change") * 100.0, 1) if delta.get("pct_change") is not None else None,
                "old_price": _round(delta.get("old_price")),
                "new_price": _round(delta.get("new_price")),
                "currency": delta.get("currency"),
                "at": s.created_at.isoformat(timespec="minutes"),
            }
        )

    # ---- Top SKUs by brand (cheapest 3 + priciest 3) — keeps the brief grounded.
    sku_samples: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for c in comps:
        # latest snapshot per active product (linear over typical sizes is fine).
        rows = []
        for p in products:
            if p.competitor_id != c.id:
                continue
            snap = db.scalar(
                select(ProductSnapshot)
                .where(ProductSnapshot.product_id == p.id)
                .order_by(ProductSnapshot.captured_at.desc())
                .limit(1)
            )
            if snap and snap.price_min and float(snap.price_min) > 0:
                rows.append((p, snap, float(snap.price_min)))
        rows.sort(key=lambda r: r[2])
        cheapest = [
            {"title": p.title, "price": _round(px), "currency": s.currency, "type": p.product_type}
            for p, s, px in rows[:3]
        ]
        priciest = [
            {"title": p.title, "price": _round(px), "currency": s.currency, "type": p.product_type}
            for p, s, px in list(reversed(rows))[:3]
        ]
        if cheapest or priciest:
            sku_samples[c.slug] = {"cheapest": cheapest, "priciest": priciest}

    # ---- Top social mentions (if any).
    top_social = []
    if _HAS_SOCIAL and SocialMention is not None:
        social_q = (
            select(SocialMention)
            .options(selectinload(SocialMention.competitor))
            .order_by(
                (SocialMention.metric_views.is_(None)),  # Nulls last
                SocialMention.metric_views.desc(),
                SocialMention.first_seen_at.desc(),
            )
            .limit(15)
        )
        try:
            for m in db.scalars(social_q):
                top_social.append(
                    {
                        "brand": m.competitor.slug if m.competitor else None,
                        "platform": m.platform,
                        "author": m.author,
                        "title": m.title[:160],
                        "views": m.metric_views,
                        "score": m.metric_score,
                        "url": m.url,
                    }
                )
        except Exception:
            top_social = []

    return {
        "as_of": utc_now().isoformat(timespec="seconds"),
        "window_days": window_days,
        "anchor": {"slug": overview.anchor_slug, "name": overview.anchor_name},
        "narrative": overview.narrative,
        "brands": brand_blocks,
        "price_landscape": overview.price_landscape,
        "discount_landscape": overview.discount_landscape,
        "stock_pressure": overview.stock_pressure,
        "anchor_whitespace": overview.anchor_whitespace,
        "top_actives_in_catalog": overview.top_actives_in_catalog,
        "active_cross_brand": overview.active_cross_brand[:15],
        "top_price_moves": overview.top_price_moves,
        "launches_per_week": overview.launches_per_week,
        "catalog_size_weekly": overview.catalog_size_weekly,
        "recent_launches_30d": overview.recent_launches_30d[:30],
        "categories": categories,
        "sku_samples_per_brand": sku_samples,
        "recent_signals": recent_signals,
        "top_social_mentions": top_social,
        "data_quality_notes": overview.data_quality_notes,
    }
