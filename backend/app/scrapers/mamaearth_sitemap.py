"""Mamaearth scraper that goes around Cloudflare/CDN bot deflection.

Mamaearth's Shopify-style endpoints (``/products.json``, ``/products/<h>.js``,
``/collections/all/products.json``) all return a tiny HTML "redirect" page
("May be you are looking for mamaearth please click here"). However:

- ``https://mamaearth.in/sitemap.xml`` is **open** (Google needs it) and lists
  every product URL.
- Each PDP returns full HTML with a ``<script type="application/ld+json">``
  block describing the product (``schema.org/Product``) including price,
  currency and availability.

So the realistic free path is **sitemap → PDP HTML → JSON-LD parse**.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from .base import BaseSource, FetchContext, RawProduct, SourceError

logger = logging.getLogger(__name__)


_LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.IGNORECASE)
_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _browser_headers(user_agent: str) -> dict[str, str]:
    """Mamaearth's CDN looks at Accept/Sec-Fetch headers to decide bot/human."""

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }


def _is_product_url(u: str, product_path: str) -> bool:
    p = urlparse(u).path
    if product_path not in p:
        return False
    if "/reviews" in p or "/review" in p.split("/")[-1]:
        return False
    return True


def _availability_to_bool(av: Any) -> bool:
    if not av:
        return True
    s = str(av).lower()
    return "instock" in s or "in_stock" in s or s.endswith("instock")


def _coerce_offers(offers: Any) -> list[dict[str, Any]]:
    if offers is None:
        return []
    if isinstance(offers, dict):
        if offers.get("@type") == "AggregateOffer":
            inner = offers.get("offers")
            if isinstance(inner, list):
                return [o for o in inner if isinstance(o, dict)]
            return [offers]
        return [offers]
    if isinstance(offers, list):
        return [o for o in offers if isinstance(o, dict)]
    return []


def _extract_product_blocks(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _LD_RE.finditer(html):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            cleaned = raw.replace("\r", " ").replace("\n", " ")
            try:
                data = json.loads(cleaned)
            except Exception:
                continue
        for block in _walk_for_product(data):
            out.append(block)
    return out


def _walk_for_product(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, list):
        for n in node:
            yield from _walk_for_product(n)
        return
    if not isinstance(node, dict):
        return
    t = node.get("@type")
    if isinstance(t, list):
        is_product = "Product" in t
    else:
        is_product = t == "Product"
    if is_product:
        yield node
    for v in node.values():
        if isinstance(v, (dict, list)):
            yield from _walk_for_product(v)


def _id_from_url(url: str) -> str:
    h = urlparse(url).path.rstrip("/").split("/")[-1] or url
    return f"mamaearth:{h}"


def _to_raw_product(url: str, blocks: list[dict[str, Any]]) -> RawProduct | None:
    if not blocks:
        return None
    p = blocks[0]
    title = p.get("name") or "(untitled)"
    image_field = p.get("image")
    if isinstance(image_field, list):
        image_url = image_field[0] if image_field else None
    elif isinstance(image_field, str):
        image_url = image_field
    else:
        image_url = None
    sku_field = p.get("sku") or p.get("productID") or p.get("mpn")
    handle = urlparse(url).path.rstrip("/").split("/")[-1] or None

    offers = _coerce_offers(p.get("offers"))
    prices: list[float] = []
    currency: str | None = None
    available_any = False
    for o in offers:
        try:
            prices.append(float(str(o.get("price"))))
        except (TypeError, ValueError):
            pass
        if currency is None:
            currency = o.get("priceCurrency")
        if _availability_to_bool(o.get("availability")):
            available_any = True
    if not offers:
        available_any = True

    price_min = min(prices) if prices else None
    price_max = max(prices) if prices else None

    brand = p.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")

    cat = p.get("category")
    if isinstance(cat, list):
        cat = cat[0] if cat else None

    return RawProduct(
        external_id=str(sku_field or _id_from_url(url)),
        handle=handle,
        title=str(title),
        product_type=str(cat) if cat else None,
        vendor=str(brand) if brand else "Mamaearth",
        url=url,
        image_url=str(image_url) if image_url else None,
        tags=[],
        price_min=price_min,
        price_max=price_max,
        currency=currency or "INR",
        available=available_any,
        variants_count=max(1, len(offers)),
        raw={"jsonld_offers": len(offers)},
    )


class MamaearthSitemapSource(BaseSource):
    """Sitemap-driven Mamaearth catalog (no provider/proxy required)."""

    kind = "mamaearth_sitemap"

    def __init__(self, url: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(url, config)
        self.product_path: str = self.config.get("product_path", "/product/")
        self.max_products: int = int(self.config.get("max_products", 60))
        self.delay_ms: int = int(self.config.get("delay_ms", 250))
        self.handle_allowlist: list[str] | None = self.config.get("handles")

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        headers = _browser_headers(ctx.user_agent)
        sitemap_url = self.url
        try:
            with httpx.Client(timeout=ctx.timeout, headers=headers, follow_redirects=True) as client:
                resp = client.get(sitemap_url)
                resp.raise_for_status()
                xml_text = resp.text
        except httpx.HTTPError as exc:
            raise SourceError(f"sitemap fetch failed: {exc}") from exc

        urls: list[str] = []
        seen: set[str] = set()
        for u in _LOC_RE.findall(xml_text):
            if not _is_product_url(u, self.product_path):
                continue
            if u in seen:
                continue
            seen.add(u)
            urls.append(u)

        if self.handle_allowlist:
            allow = set(self.handle_allowlist)
            urls = [u for u in urls if (urlparse(u).path.rstrip("/").split("/")[-1] or "") in allow]

        if self.max_products and self.max_products > 0:
            urls = urls[: self.max_products]

        logger.info("mamaearth_sitemap planning fetch product_count=%s", len(urls))
        if not urls:
            return

        with httpx.Client(timeout=ctx.timeout, headers=headers, follow_redirects=True) as client:
            for i, u in enumerate(urls, 1):
                try:
                    r = client.get(u)
                    if r.status_code != 200 or len(r.text) < 5000:
                        logger.warning(
                            "mamaearth pdp skipped status=%s len=%s url=%s",
                            r.status_code,
                            len(r.text),
                            u,
                        )
                        continue
                    blocks = _extract_product_blocks(r.text)
                    rp = _to_raw_product(u, blocks)
                    if rp is None:
                        logger.warning("mamaearth pdp no Product JSON-LD url=%s", u)
                        continue
                    yield rp
                except httpx.HTTPError as exc:
                    logger.warning("mamaearth pdp fetch failed url=%s err=%s", u, exc)
                if self.delay_ms > 0:
                    time.sleep(self.delay_ms / 1000.0)
                if i % 25 == 0:
                    logger.info("mamaearth_sitemap progress %s/%s", i, len(urls))
