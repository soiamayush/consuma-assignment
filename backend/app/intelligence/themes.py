"""Lightweight keyword-based theme classifier.

We keep this rule-based on purpose: it's explainable, deterministic, and
doesn't require an LLM key for the assignment. The `classify` function is
easy to swap for an embedding-based classifier later.
"""

from __future__ import annotations

import re

# Ordered so earlier rules win ties.
THEMES: list[tuple[str, list[str]]] = [
    ("launch", ["launch", "launches", "launched", "introducing", "debut", "unveil", "new drop", "just dropped"]),
    ("collaboration", ["collab", "collaboration", "x ", "partnership", "teams up", "partners with"]),
    ("sustainability", ["sustainab", "organic", "recycled", "regenerative", "carbon", "eco-", "plant-based", "bio-based"]),
    ("expansion", ["flagship", "store opens", "opens in", "new store", "pop-up", "expands to", "retail"]),
    ("pricing", ["sale", "discount", "% off", "markdown", "promo", "bundle", "price drop"]),
    ("collection", ["collection", "capsule", "edition", "lineup", "range"]),
    ("sold_out", ["sold out", "restock", "waitlist", "back in stock"]),
    ("clinical", ["clinical", "dermatologist", "tolerability", "patch test", "efficacy"]),
    ("spf", ["spf", "sunscreen", "uva", "uvb", "broad spectrum"]),
]


def classify(text: str | None) -> list[str]:
    if not text:
        return []
    t = text.lower()
    hits: list[str] = []
    for theme, keywords in THEMES:
        for kw in keywords:
            # Use word boundary where sensible, substring for multi-word phrases.
            pattern = rf"\b{re.escape(kw)}\b" if " " not in kw and "-" not in kw else re.escape(kw)
            if re.search(pattern, t):
                hits.append(theme)
                break
    return hits


def classify_many(texts: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in texts:
        for theme in classify(t):
            if theme not in seen:
                seen.add(theme)
                out.append(theme)
    return out
