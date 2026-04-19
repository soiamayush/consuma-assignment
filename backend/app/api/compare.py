"""Cross-brand price + catalog comparison ("Compare" page).

Single endpoint that powers the "everything in one place" comparison view:

    GET /api/compare?category=Serum&keyword=vitamin+c

For the chosen scope (a ``product_type`` and/or title keyword) it returns, per
brand:

* SKU count in scope
* p25 / median / p75 price band  + min / max
* discount share + median % off (in scope)
* % anchor delta (peer median vs anchor median, signed)
* the **3 cheapest** and **3 most expensive** SKUs with image / url / price
* one ranked list of all SKUs in scope (used by the UI's expandable table)

Plus a ``categories`` list (top product_types with totals) and a
``keyword_suggestions`` list of common nouns from titles, so the UI can offer
a usable picker out of the box.

All logic is computed from the latest ``ProductSnapshot`` per active product —
no historical aggregation, so the response stays fast even on SQLite.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Competitor, Product, ProductSnapshot

router = APIRouter(prefix="/api/compare", tags=["compare"])


# --- helpers --------------------------------------------------------------

def _percentile(vals: list[float], q: float) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return round(s[0], 2)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return round(s[lo], 2)
    return round(s[lo] + (s[hi] - s[lo]) * (pos - lo), 2)


def _median(vals: list[float]) -> Optional[float]:
    return _percentile(vals, 0.5)


def _latest_snapshot(db: Session, product_id: int) -> Optional[ProductSnapshot]:
    return db.scalar(
        select(ProductSnapshot)
        .where(ProductSnapshot.product_id == product_id)
        .order_by(ProductSnapshot.captured_at.desc())
        .limit(1)
    )


_STOPWORDS = {
    "the", "and", "for", "with", "your", "our", "from", "into",
    "this", "that", "best", "skin", "skincare", "care", "new",
    "pack", "set", "kit", "ml", "g", "gm", "size", "value", "trial",
    "combo", "limited", "edition", "free", "sample",
}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]{2,}")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def _passes_filter(p: Product, category: str | None, keyword: str | None) -> bool:
    if category:
        cat = (p.product_type or "").strip().lower()
        if cat != category.strip().lower():
            return False
    if keyword:
        kw = keyword.strip().lower()
        if not kw:
            return True
        hay = " ".join(filter(None, [p.title or "", p.product_type or "", " ".join(p.tags or [])])).lower()
        if kw not in hay:
            return False
    return True


def _sku_payload(p: Product, snap: ProductSnapshot | None) -> dict[str, Any]:
    return {
        "id": p.id,
        "title": p.title,
        "url": p.url,
        "image_url": p.image_url,
        "price_min": float(snap.price_min) if snap and snap.price_min is not None else None,
        "price_max": float(snap.price_max) if snap and snap.price_max is not None else None,
        "compare_at_min": float(snap.compare_at_min) if snap and snap.compare_at_min is not None else None,
        "compare_at_max": float(snap.compare_at_max) if snap and snap.compare_at_max is not None else None,
        "currency": snap.currency if snap else None,
    }


# --- endpoints ------------------------------------------------------------

@router.get("")
def compare(
    category: Optional[str] = Query(None, description="Filter by product_type (case-insensitive)"),
    keyword: Optional[str] = Query(None, description="Substring match on title / tags / product_type"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    comps = list(
        db.scalars(
            select(Competitor).order_by(Competitor.is_anchor.desc(), Competitor.brand_weight.desc())
        )
    )
    anchor = next((c for c in comps if c.is_anchor), None)

    # Pull all active products with their competitor relationship pre-loaded.
    products = list(
        db.scalars(
            select(Product)
            .options(selectinload(Product.competitor))
            .where(Product.is_active.is_(True))
        )
    )

    # Build category ladder once (over the whole catalog, not the filter — so
    # the picker shows real options even when a filter is active).
    cat_counter: Counter[str] = Counter()
    token_counter: Counter[str] = Counter()
    for p in products:
        ct = (p.product_type or "").strip()
        if ct:
            cat_counter[ct] += 1
        token_counter.update(_tokens(p.title or ""))

    categories = [
        {"category": ct, "sku_count": n}
        for ct, n in cat_counter.most_common(40)
    ]
    keyword_suggestions = [
        {"keyword": tk, "hits": n}
        for tk, n in token_counter.most_common(25)
        if n >= 3 and len(tk) >= 4
    ]

    # Prefetch latest snapshot for every product in scope. We do it lazily so
    # we don't pay for SKUs the filter rejects.
    in_scope: list[tuple[Product, ProductSnapshot | None]] = []
    for p in products:
        if not _passes_filter(p, category, keyword):
            continue
        snap = _latest_snapshot(db, p.id)
        in_scope.append((p, snap))

    # Group by competitor.
    by_brand: dict[int, list[tuple[Product, ProductSnapshot | None]]] = defaultdict(list)
    for p, snap in in_scope:
        by_brand[p.competitor_id].append((p, snap))

    # Compute the anchor median first so we can express deltas relative to it.
    anchor_median: float | None = None
    if anchor:
        a_prices = [
            float(s.price_min)
            for _p, s in by_brand.get(anchor.id, [])
            if s and s.price_min is not None and float(s.price_min) > 0
        ]
        anchor_median = _median(a_prices) if a_prices else None

    per_brand: list[dict[str, Any]] = []
    for c in comps:
        rows = by_brand.get(c.id, [])
        prices: list[float] = []
        currencies: set[str] = set()
        discounted = 0
        priceable = 0
        discount_pcts: list[float] = []
        for p, snap in rows:
            if snap and snap.price_min is not None:
                px = float(snap.price_min)
                if px > 0:
                    prices.append(px)
                    if snap.currency:
                        currencies.add(snap.currency)
                    priceable += 1
                    cap = snap.compare_at_min
                    if cap is not None and float(cap) > px:
                        discounted += 1
                        discount_pcts.append(round((float(cap) - px) / float(cap) * 100.0, 2))

        median = _median(prices)
        ranked = sorted(
            (r for r in rows if r[1] and r[1].price_min is not None and float(r[1].price_min) > 0),
            key=lambda r: float(r[1].price_min),
        )
        cheapest = [_sku_payload(p, s) for p, s in ranked[:3]]
        most_expensive = [_sku_payload(p, s) for p, s in list(reversed(ranked))[:3]]
        all_skus = [_sku_payload(p, s) for p, s in ranked]

        anchor_delta_pct: float | None = None
        if anchor_median and median is not None:
            anchor_delta_pct = round((median - anchor_median) / anchor_median * 100.0, 1)

        currency = next(iter(currencies)) if len(currencies) == 1 else ("mixed" if currencies else None)

        per_brand.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "sku_count": len(rows),
                "priceable_skus": priceable,
                "currency": currency,
                "min_price": round(min(prices), 2) if prices else None,
                "max_price": round(max(prices), 2) if prices else None,
                "p25": _percentile(prices, 0.25),
                "median": median,
                "p75": _percentile(prices, 0.75),
                "discount_share_pct": round((discounted / priceable * 100.0), 1) if priceable else 0.0,
                "median_discount_pct": _median(discount_pcts) or 0.0,
                "max_discount_pct": round(max(discount_pcts), 1) if discount_pcts else 0.0,
                "anchor_delta_pct": anchor_delta_pct,
                "cheapest": cheapest,
                "most_expensive": most_expensive,
                "all_skus": all_skus[:60],  # cap so payload stays bounded
            }
        )

    # Total in-scope SKUs (across brands). Anchor SKUs reported separately so
    # the UI can show "(of which 14 are yours)" style context.
    in_scope_total = len(in_scope)
    anchor_in_scope = len(by_brand.get(anchor.id, [])) if anchor else 0

    return {
        "scope": {
            "category": category,
            "keyword": keyword,
            "in_scope_total": in_scope_total,
            "anchor_in_scope": anchor_in_scope,
        },
        "anchor_slug": anchor.slug if anchor else None,
        "anchor_name": anchor.name if anchor else None,
        "anchor_median_price": anchor_median,
        "categories": categories,
        "keyword_suggestions": keyword_suggestions,
        "per_brand": per_brand,
    }
