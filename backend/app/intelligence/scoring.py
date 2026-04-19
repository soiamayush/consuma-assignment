"""Importance scoring for signals.

The score is a 0..1 value combining:
  - base weight per kind (launches/price drops rank higher than minor tweaks)
  - recency decay (halflife ~ 7 days)
  - magnitude (e.g. |% price change|, new-product count)
  - brand weight (an editorial prior on how closely we care about this brand)
  - theme boost (launches/collaborations/sustainability stories get a nudge)

Kept intentionally simple + explainable — every term shows up in `delta.score_breakdown`.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

BASE_KIND_WEIGHT: dict[str, float] = {
    "PRODUCT_LAUNCH": 0.80,
    "PRODUCT_REMOVED": 0.35,
    "PRICE_DROP": 0.75,
    "PRICE_INCREASE": 0.55,
    "BACK_IN_STOCK": 0.45,
    "OUT_OF_STOCK": 0.40,
    "BLOG_POST": 0.50,
    "CATALOG_SURGE": 0.95,
}

THEME_BOOST: dict[str, float] = {
    "launch": 0.10,
    "collaboration": 0.12,
    "sustainability": 0.07,
    "expansion": 0.08,
    "pricing": 0.05,
    "collection": 0.06,
    "sold_out": 0.04,
}


def recency_decay(created_at: datetime, halflife_days: float = 7.0, now: datetime | None = None) -> float:
    # Normalize both sides to naive UTC so we never raise on mixed tz.
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    elif now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    ca = created_at
    if ca.tzinfo is not None:
        ca = ca.astimezone(timezone.utc).replace(tzinfo=None)
    age_days = max(0.0, (now - ca).total_seconds() / 86400.0)
    return math.pow(0.5, age_days / halflife_days)


def magnitude_factor(kind: str, delta: dict[str, Any]) -> float:
    """Maps a change magnitude to a 0..1 multiplier."""
    if kind in ("PRICE_DROP", "PRICE_INCREASE"):
        pct = abs(float(delta.get("pct_change") or 0.0))
        # 0% -> 0.3, 10% -> 0.7, 25% -> 0.9, 50%+ -> 1.0
        return min(1.0, 0.3 + pct * 2.8)
    if kind == "CATALOG_SURGE":
        n = int(delta.get("new_products") or 0)
        return min(1.0, 0.4 + n / 20.0)
    if kind == "PRODUCT_LAUNCH":
        return 1.0
    if kind == "BLOG_POST":
        return 0.8
    return 0.6


def score_signal(
    kind: str,
    created_at: datetime,
    delta: dict[str, Any],
    themes: list[str],
    brand_weight: float,
) -> tuple[float, dict[str, float]]:
    base = BASE_KIND_WEIGHT.get(kind, 0.4)
    recency = recency_decay(created_at)
    magnitude = magnitude_factor(kind, delta)
    theme_boost = sum(THEME_BOOST.get(t, 0.0) for t in themes)
    raw = base * (0.55 + 0.45 * magnitude) * (0.5 + 0.5 * recency) * (0.6 + 0.4 * brand_weight) + theme_boost
    score = max(0.0, min(1.0, raw))
    breakdown = {
        "base": round(base, 3),
        "magnitude": round(magnitude, 3),
        "recency": round(recency, 3),
        "brand_weight": round(brand_weight, 3),
        "theme_boost": round(theme_boost, 3),
        "final": round(score, 3),
    }
    return score, breakdown
