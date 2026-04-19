"""Generic HTML PLP scraper for non-Shopify stores.

Approach: pull the listing page through the proxy provider (so we can render
or rotate IPs) and parse with **selectolax** (fast C parser, ~10x BeautifulSoup).
Then optionally fan-out to PDP pages to enrich each product (price, tags,
description) — gated by ``max_pdp`` to keep run-time bounded.

Config schema::

    url: PLP URL (paginate by appending ``?page=N`` if ``paginate=true``)
    config:
      store: shopper-facing host
      product_card_selector: CSS for cards
      title_selector: CSS for title (relative to card)
      price_selector: CSS for price
      link_selector: CSS for anchor (defaults to the card if it's an <a>)
      image_selector: CSS for image src
      paginate: bool (default false)
      max_pages: int (default 3)
      max_pdp: int (default 0)  -- set >0 to enrich each card via PDP
      pdp_price_selector: CSS for price on PDP page
      pdp_tags_selector: CSS for tag chips on PDP

The HTTP layer goes through ``proxy.get_text_via_provider`` so a single env
var (``SCRAPERAPI_KEY`` or ``SCRAPER_PROXY_URL``) is all the user needs to
flip on third-party scraping.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from .base import BaseSource, FetchContext, RawProduct, SourceError
from .proxy import get_text_via_provider

logger = logging.getLogger(__name__)


_PRICE_RE = re.compile(r"(\d[\d,]*\.?\d*)")


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\u20b9", "").replace("Rs.", "").replace(",", "")
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _import_selectolax():
    try:
        from selectolax.parser import HTMLParser  # type: ignore
        return HTMLParser
    except ImportError as exc:  # pragma: no cover
        raise SourceError(
            "selectolax not installed. Add `selectolax` to requirements.txt"
        ) from exc


class HtmlListingSource(BaseSource):
    kind = "html_listing"

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        HTMLParser = _import_selectolax()

        cfg = self.config
        store = cfg.get("store") or ""
        card_sel = cfg.get("product_card_selector") or "a[href*='/product']"
        title_sel = cfg.get("title_selector")
        price_sel = cfg.get("price_selector")
        link_sel = cfg.get("link_selector")
        image_sel = cfg.get("image_selector", "img")
        paginate = bool(cfg.get("paginate"))
        max_pages = int(cfg.get("max_pages", 3 if paginate else 1))
        max_pdp = int(cfg.get("max_pdp", 0))
        pdp_price_sel = cfg.get("pdp_price_selector")
        pdp_tags_sel = cfg.get("pdp_tags_selector")
        currency = cfg.get("currency")
        render_js = bool(cfg.get("render_js", False))
        country = cfg.get("country")

        seen = 0

        for page in range(1, max_pages + 1):
            page_url = f"{self.url}?page={page}" if paginate and page > 1 else self.url
            try:
                html = get_text_via_provider(
                    page_url,
                    timeout=ctx.timeout,
                    user_agent=ctx.user_agent,
                    render_js=render_js,
                    country=country,
                )
            except Exception as exc:
                logger.warning("html_listing fetch failed page=%s err=%s", page, exc)
                break

            tree = HTMLParser(html)
            cards = tree.css(card_sel)
            if not cards:
                logger.info("html_listing no cards page=%s url=%s", page, page_url)
                break

            for card in cards:
                title_node = card.css_first(title_sel) if title_sel else card
                price_node = card.css_first(price_sel) if price_sel else None
                link_node = card.css_first(link_sel) if link_sel else (card if card.tag == "a" else card.css_first("a"))
                img_node = card.css_first(image_sel) if image_sel else None

                title = (title_node.text(strip=True) if title_node else "").strip()
                if not title:
                    continue
                price = _parse_price(price_node.text(strip=True) if price_node else None)
                href = (link_node.attributes.get("href") if link_node else "") or ""
                if href and not href.startswith("http"):
                    href = urljoin(f"https://{store}", href)
                image = (img_node.attributes.get("src") or img_node.attributes.get("data-src")) if img_node else None
                handle = href.rstrip("/").rsplit("/", 1)[-1] if href else title.lower().replace(" ", "-")[:80]

                tags: list[str] = []
                if max_pdp and seen < max_pdp and href:
                    try:
                        pdp_html = get_text_via_provider(
                            href, timeout=ctx.timeout, user_agent=ctx.user_agent, render_js=render_js, country=country
                        )
                        pdp_tree = HTMLParser(pdp_html)
                        if pdp_price_sel:
                            pp = _parse_price(pdp_tree.css_first(pdp_price_sel).text(strip=True) if pdp_tree.css_first(pdp_price_sel) else None)
                            if pp is not None:
                                price = pp
                        if pdp_tags_sel:
                            tags = [n.text(strip=True) for n in pdp_tree.css(pdp_tags_sel) if n.text(strip=True)]
                    except Exception as exc:
                        logger.debug("PDP enrich skipped href=%s err=%s", href, exc)

                seen += 1

                yield RawProduct(
                    external_id=handle,
                    handle=handle,
                    title=title,
                    product_type=cfg.get("product_type"),
                    vendor=store,
                    url=href or None,
                    image_url=image,
                    tags=tags,
                    price_min=price,
                    price_max=price,
                    currency=currency,
                    available=True,
                    variants_count=1,
                    raw={"source": "html_listing", "page": page},
                )

            if not paginate:
                break
