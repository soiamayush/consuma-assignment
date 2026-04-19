"""Shopify public `/products.json` source.

Most Shopify stores expose `/products.json` which returns up to 250 items
with a `page` query param. We paginate until a page returns empty or we hit
`max_pages` (safety bound).

**Pricing rules (important for India storefronts like Minimalist):**

- ``variant.price`` = **current sale / list price** the customer pays (e.g. ₹584).
- ``variant.compare_at_price`` = **MSRP / struck-through** anchor when on sale (e.g. ₹649).
- We store sale prices in ``price_min`` / ``price_max`` and MSRP in
  ``compare_at_min`` / ``compare_at_max`` on snapshots so the UI never
  confuses the two.
- Public JSON usually omits ``presentment_prices``; we infer **INR** for
  known India hosts so analytics are not mislabeled as USD.
- Some catalogs carry **stray low variants** (samples, mis-priced SKUs). When
  several variant prices disagree badly, we **trim** obvious outliers before
  min/max so ``₹31`` next to ``₹400+`` does not become the headline price.
- **B1G1 / member / cart promos** on the PDP are often **not** in
  ``products.json``; the JSON reflects the **base variant list price** (e.g.
  Pilgrim 10% Niacinamide = ``499`` / ``compare_at 595`` today), not the
  bundled checkout total.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from .base import BaseSource, FetchContext, RawProduct, http_get_json

logger = logging.getLogger(__name__)


def _infer_currency(store_base: str | None) -> str | None:
    if not store_base:
        return None
    host = (urlparse(store_base).hostname or "").lower()
    if host.endswith(".in") or host in (
        "www.beminimalist.co",
        "beminimalist.co",
        "mamaearth.in",
        "www.mamaearth.in",
        "discoverpilgrim.com",
        "www.bellavitaorganic.com",
        "bellavitaorganic.com",
        "thedeconstruct.in",
        "www.thedeconstruct.in",
        "foxtale.in",
        "www.foxtale.in",
    ):
        return "INR"
    if "myshopify.com" in host and (
        "foxtale" in host or "deconstruct" in host or "mamaearth" in host or "pilgrim" in host
    ):
        return "INR"
    return None


def _median_sorted(s: list[float]) -> float:
    n = len(s)
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


def _trim_sale_prices(prices: list[float]) -> list[float]:
    """Drop rock-bottom variant prices that are clearly not the main SKU band."""
    pos = [p for p in prices if p is not None and p > 0]
    if len(pos) <= 2:
        return pos
    s = sorted(pos)
    med = _median_sorted(s)
    if med <= 0:
        return s
    kept = [p for p in s if not (p < med * 0.2 and max(s) / p > 6.0)]
    return kept if len(kept) >= 1 else s


def _float_variant(v: dict[str, Any], key: str) -> float | None:
    raw = v.get(key)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _price_of(variants: list[dict[str, Any]]) -> tuple[float | None, float | None, str | None]:
    """Sale / current prices from ``variant.price`` only (never compare_at)."""
    prices: list[float] = []
    currency: str | None = None
    for v in variants:
        p = _float_variant(v, "price")
        if p is not None:
            prices.append(p)
        if currency is None:
            pp = v.get("presentment_prices") or []
            if pp and isinstance(pp, list):
                first = pp[0] if isinstance(pp[0], dict) else {}
                price_obj = first.get("price") if isinstance(first, dict) else None
                if isinstance(price_obj, dict):
                    currency = price_obj.get("currency_code")
    if not prices:
        return None, None, currency
    trimmed = _trim_sale_prices(prices)
    # All variants priced at 0 (gift cards, hidden SKUs, draft products) — keep the
    # product but with a null price band so the catalog does not silently lose rows.
    if not trimmed:
        return None, None, currency
    if len(trimmed) < len(prices):
        logger.debug(
            "shopify variant price trim: raw=%s kept=%s",
            sorted(prices),
            trimmed,
        )
    return min(trimmed), max(trimmed), currency


def _compare_at_of(variants: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    caps: list[float] = []
    for v in variants:
        c = _float_variant(v, "compare_at_price")
        if c is not None and c > 0:
            caps.append(c)
    if not caps:
        return None, None
    return min(caps), max(caps)


def _availability(variants: list[dict[str, Any]]) -> bool:
    return any(v.get("available", False) for v in variants)


class ShopifyProductsSource(BaseSource):
    kind = "shopify_products"

    def __init__(self, url: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(url, config)
        self.per_page = int(self.config.get("per_page", 250))

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        base = self.url.rstrip("/")
        if not base.endswith("products.json"):
            base = urljoin(base + "/", "products.json")

        for page in range(1, ctx.max_pages + 1):
            page_url = f"{base}?limit={self.per_page}&page={page}"
            logger.info("shopify_products fetch page=%s url=%s", page, page_url)
            data = http_get_json(page_url, ctx)
            products = data.get("products") or []
            if not products:
                break
            for p in products:
                try:
                    yield self._parse(p)
                except Exception as exc:
                    logger.warning("skip product parse error pid=%s err=%s", p.get("id"), exc)
            if len(products) < self.per_page:
                break

    def _parse(self, p: dict[str, Any]) -> RawProduct:
        variants = p.get("variants") or []
        price_min, price_max, currency = _price_of(variants)
        ca_min, ca_max = _compare_at_of(variants)
        store_base = self._store_base()
        if currency is None:
            currency = _infer_currency(store_base)

        images = p.get("images") or []
        image_url = None
        if images:
            image_url = images[0].get("src")
        tags = p.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        handle = p.get("handle")
        url = f"{store_base}/products/{handle}" if handle and store_base else None
        return RawProduct(
            external_id=str(p.get("id")),
            handle=handle,
            title=p.get("title") or "(untitled)",
            product_type=p.get("product_type"),
            vendor=p.get("vendor"),
            url=url,
            image_url=image_url,
            tags=list(tags),
            price_min=price_min,
            price_max=price_max,
            currency=currency,
            available=_availability(variants),
            variants_count=len(variants),
            raw={
                "published_at": p.get("published_at"),
                "updated_at": p.get("updated_at"),
                "compare_at_min": ca_min,
                "compare_at_max": ca_max,
            },
        )

    def _store_base(self) -> str | None:
        u = self.url
        if "/products.json" in u:
            return u.split("/products.json")[0]
        return u.rstrip("/")
