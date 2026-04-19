"""MyGlamm scraper.

The myglamm.com storefront is a React app whose product data is served by a
public-but-undocumented internal API at ``api.myglamm.com``. Hitting it
requires a few standard headers (Origin/Referer/UA). Inside a corporate
environment / CI runner these requests are often rate-limited from raw
datacentre IPs, so the request goes through ``proxy.get_text_via_provider``
— set ``SCRAPERAPI_KEY`` or ``SCRAPER_PROXY_URL`` to route around it.

If the JSON endpoint blocks (403 / 429 / Cloudflare), the seed wires a second
``browser_listing`` Source pointed at ``/skincare`` that drives Playwright
through the *same* proxy and falls back to DOM scraping. Both Sources stream
into the same ingestion runner, so analytics see one merged catalog.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from .base import BaseSource, FetchContext, RawProduct, SourceError
from .proxy import get_json_via_provider

logger = logging.getLogger(__name__)


# Field names the myglamm response uses (best-effort; their schema isn't versioned).
_TITLE_KEYS = ("displayName", "name", "title", "productName")
_PRICE_KEYS = ("price", "discountedPrice", "sellingPrice")
_IMAGE_KEYS = ("featuredImage", "image", "imageUrl", "thumbnail")


def _first(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


class MyGlammApiSource(BaseSource):
    kind = "myglamm_internal_api"

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        cfg = self.config
        categories = cfg.get("categories") or ["skincare"]
        max_pages = int(cfg.get("max_pages", 3))
        per_page = int(cfg.get("per_page", 24))
        country = cfg.get("country") or "IN"

        for cat in categories:
            for page in range(1, max_pages + 1):
                url = (
                    f"{self.url}?category={cat}&page={page}&limit={per_page}"
                    f"&country={country}"
                )
                try:
                    data = get_json_via_provider(
                        url,
                        timeout=ctx.timeout,
                        user_agent=ctx.user_agent,
                        render_js=False,
                        country=country.lower() if country else None,
                    )
                except Exception as exc:
                    logger.warning("myglamm api fetch failed cat=%s page=%s err=%s", cat, page, exc)
                    if page == 1:
                        # First page failed → bubble up so the IngestionRun records the error
                        # and the operator can flip on the browser fallback.
                        raise SourceError(f"myglamm api category={cat}: {exc}")
                    break

                items = self._extract_items(data)
                if not items:
                    logger.info("myglamm api empty cat=%s page=%s", cat, page)
                    break

                for it in items:
                    title = _first(it, _TITLE_KEYS)
                    if not title:
                        continue
                    price_raw = _first(it, _PRICE_KEYS)
                    try:
                        price = float(price_raw) if price_raw is not None else None
                    except (TypeError, ValueError):
                        price = None
                    image = _first(it, _IMAGE_KEYS)
                    if isinstance(image, dict):
                        image = image.get("url") or image.get("src")
                    handle = it.get("slug") or it.get("urlKey") or str(it.get("id") or title)[:80]
                    pid = str(it.get("id") or it.get("_id") or handle)
                    yield RawProduct(
                        external_id=pid,
                        handle=handle,
                        title=title,
                        product_type=it.get("category") or it.get("subCategory"),
                        vendor="myglamm",
                        url=f"https://www.myglamm.com/product/{handle}",
                        image_url=image if isinstance(image, str) else None,
                        tags=list(it.get("tags") or []) if isinstance(it.get("tags"), list) else [],
                        price_min=price,
                        price_max=price,
                        currency="INR",
                        available=bool(it.get("inStock", True)),
                        variants_count=len(it.get("variants") or [None]) or 1,
                        raw={"source": "myglamm_api", "category": cat, "page": page},
                    )

                if len(items) < per_page:
                    break

    @staticmethod
    def _extract_items(data: Any) -> list[dict[str, Any]]:
        """MyGlamm wraps results inconsistently across endpoints; try common shells."""
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if not isinstance(data, dict):
            return []
        for path in (
            ("data", "products"),
            ("data", "items"),
            ("result", "products"),
            ("products",),
            ("items",),
        ):
            cur: Any = data
            for k in path:
                cur = cur.get(k) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, list) and cur and isinstance(cur[0], dict):
                return cur
        return []
