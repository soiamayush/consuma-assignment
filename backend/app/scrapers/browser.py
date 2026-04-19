"""Headless-browser scraper source.

For sites that ship product data only after JS hydration (or aggressively gate
HTTP scraping), we drive a real Chromium via Playwright. Two modes:

1. ``capture_xhr=True`` (preferred when known): visit the listing URL, intercept
   any XHR/fetch matching ``api_pattern`` and parse JSON as products. This is
   essentially "session-based scraping" — we let the SPA do its own auth /
   bot-checks, then read what it would have rendered.
2. DOM scrape: wait for ``wait_for_selector``, scroll N times to trigger lazy
   loading, then extract product cards using CSS selectors.

Playwright is **optional**. If the package or browsers are not installed we
raise a ``SourceError`` that the runner records on the IngestionRun row, so
the rest of the pipeline keeps working. Install with::

    pip install playwright
    python -m playwright install --with-deps chromium

In Docker, the ``worker`` image installs Chromium automatically.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from .base import BaseSource, FetchContext, RawProduct, SourceError

logger = logging.getLogger(__name__)


def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"(\d+[\.,]?\d*)", s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


class BrowserListingSource(BaseSource):
    """Generic Playwright source.

    Required ``config`` keys:
      - ``store``           shopper-facing host (used to build product URLs)
      - One of:
        - ``api_pattern`` + ``capture_xhr=True`` → intercept JSON responses
        - ``product_card_selector`` (+ optional title/price/image selectors)

    Optional:
      - ``wait_for_selector`` — wait until visible before extracting
      - ``scroll_steps``     — N page-down scrolls (lazy loading) (default 4)
      - ``json_path``        — dotted path inside captured JSON to product list
    """

    kind = "browser_listing"

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as exc:  # pragma: no cover - env dependent
            raise SourceError(
                "playwright not installed. `pip install playwright && python -m playwright install chromium`"
            ) from exc

        proxy_url = os.environ.get("SCRAPER_PROXY_URL")
        capture_xhr = bool(self.config.get("capture_xhr"))
        api_pattern = self.config.get("api_pattern")
        store = self.config.get("store") or ""
        scroll_steps = int(self.config.get("scroll_steps", 4))
        wait_sel = self.config.get("wait_for_selector")

        captured_payloads: list[Any] = []

        with sync_playwright() as pw:
            launch_kwargs: dict[str, Any] = {"headless": True}
            if proxy_url:
                launch_kwargs["proxy"] = {"server": proxy_url}
            browser = pw.chromium.launch(**launch_kwargs)
            ctx_browser = browser.new_context(user_agent=ctx.user_agent)
            page = ctx_browser.new_page()

            if capture_xhr and api_pattern:
                pat = re.compile(api_pattern)

                def _on_response(resp):  # type: ignore[no-untyped-def]
                    try:
                        if pat.search(resp.url) and resp.ok:
                            ct = resp.headers.get("content-type", "")
                            if "json" in ct:
                                captured_payloads.append(resp.json())
                    except Exception as exc:
                        logger.debug("xhr parse skip url=%s err=%s", resp.url, exc)

                page.on("response", _on_response)

            try:
                page.goto(self.url, wait_until="domcontentloaded", timeout=int(ctx.timeout * 1000))
                if wait_sel:
                    try:
                        page.wait_for_selector(wait_sel, timeout=int(ctx.timeout * 1000))
                    except Exception as exc:
                        logger.warning("wait_for_selector miss sel=%s err=%s", wait_sel, exc)
                for _ in range(scroll_steps):
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(700)
            finally:
                # Keep going even if navigation partially failed; we may still have XHR data.
                pass

            if capture_xhr and captured_payloads:
                yield from self._from_payloads(captured_payloads, store)
                browser.close()
                return

            cards = page.query_selector_all(self.config.get("product_card_selector", "a[href*='/product']"))
            logger.info("browser_listing extracted card_count=%d url=%s", len(cards), self.url)

            for card in cards[: self.config.get("max_items", 200)]:
                title_sel = self.config.get("title_selector")
                price_sel = self.config.get("price_selector")
                img_sel = self.config.get("image_selector", "img")

                title_el = card.query_selector(title_sel) if title_sel else card
                price_el = card.query_selector(price_sel) if price_sel else None
                img_el = card.query_selector(img_sel) if img_sel else None

                title = (title_el.inner_text().strip() if title_el else "").splitlines()[0]
                price = _to_float(price_el.inner_text() if price_el else None)
                href = card.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = urljoin(f"https://{store}", href)
                image = img_el.get_attribute("src") if img_el else None
                handle = href.rstrip("/").rsplit("/", 1)[-1] if href else None

                if not title:
                    continue

                yield RawProduct(
                    external_id=handle or title.lower().replace(" ", "-")[:80],
                    handle=handle,
                    title=title,
                    product_type=None,
                    vendor=store,
                    url=href or None,
                    image_url=image,
                    tags=[],
                    price_min=price,
                    price_max=price,
                    currency=self.config.get("currency"),
                    available=True,
                    variants_count=1,
                    raw={"source": "browser_listing"},
                )

            browser.close()

    def _from_payloads(self, payloads: list[Any], store: str) -> Iterable[RawProduct]:
        json_path = self.config.get("json_path", "")
        for blob in payloads:
            items = blob
            for part in [p for p in json_path.split(".") if p]:
                if isinstance(items, dict):
                    items = items.get(part)
                else:
                    items = None
                    break
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                title = it.get("title") or it.get("name") or it.get("productName")
                if not title:
                    continue
                price = it.get("price") or (it.get("variants") or [{}])[0].get("price")
                handle = it.get("slug") or it.get("handle") or str(it.get("id") or title)[:80]
                yield RawProduct(
                    external_id=str(it.get("id") or handle),
                    handle=handle,
                    title=title,
                    product_type=it.get("category") or it.get("product_type"),
                    vendor=store,
                    url=it.get("url") or (f"https://{store}/p/{handle}" if store else None),
                    image_url=(it.get("images") or [None])[0]
                    if isinstance(it.get("images"), list)
                    else it.get("image"),
                    tags=list(it.get("tags") or []) if isinstance(it.get("tags"), list) else [],
                    price_min=_to_float(str(price)) if price is not None else None,
                    price_max=_to_float(str(price)) if price is not None else None,
                    currency=it.get("currency") or self.config.get("currency"),
                    available=bool(it.get("available", True)),
                    variants_count=len(it.get("variants") or [None]) or 1,
                    raw={"source": "browser_xhr", "captured_keys": sorted(it.keys())[:8]},
                )
