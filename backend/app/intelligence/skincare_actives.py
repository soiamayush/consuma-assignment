"""Extract skincare actives / concerns from product titles and tags (rule-based).

Used by the analytics layer for differentiation: portfolio composition vs peers,
not only raw price signals.
"""

from __future__ import annotations

# (canonical_id, substring) — order matters for display priority.
ACTIVE_PATTERNS: list[tuple[str, str]] = [
    ("niacinamide", "niacinamide"),
    ("salicylic_acid", "salicylic"),
    ("glycolic_acid", "glycolic"),
    ("lactic_acid", "lactic acid"),
    ("vitamin_c", "vitamin c"),
    ("ascorbic", "ascorbic"),
    ("retinol", "retinol"),
    ("retinoid", "retinoid"),
    ("hyaluronic", "hyaluronic"),
    ("ceramide", "ceramide"),
    ("peptide", "peptide"),
    ("pdrn", "pdrn"),
    ("spf", "spf"),
    ("sunscreen", "sunscreen"),
    ("azelaic", "azelaic"),
    ("tranexamic", "tranexamic"),
    ("kojic", "kojic"),
    ("bha", "bha"),
    ("aha", "aha"),
    ("panthenol", "panthenol"),
    ("b12", "b12"),
    ("niacin", "niacin"),
]


def extract_from_text(text: str | None) -> list[str]:
    if not text:
        return []
    t = text.lower()
    out: list[str] = []
    for slug, needle in ACTIVE_PATTERNS:
        if needle in t and slug not in out:
            out.append(slug)
    return out


def extract_from_product(title: str | None, tags: list | None, product_type: str | None) -> list[str]:
    parts = [title or "", product_type or "", " ".join(tags or [])]
    merged = " | ".join(parts)
    return extract_from_text(merged)
