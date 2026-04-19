"""Third-party proxy / scraping-API integration (BYO key via env).

We support two industry-standard providers without locking to either:

- **ScraperAPI** (`SCRAPERAPI_KEY`): wrap any URL via
  ``http://api.scraperapi.com/?api_key=...&url=...&render=true``. Renders JS,
  handles rotating IPs, captchas; great for getting through Cloudflare on
  ``mamaearth.in`` / ``myglamm.com`` from a server.
- **Generic HTTP/SOCKS proxy** (`SCRAPER_PROXY_URL`, e.g. Bright Data,
  Smartproxy, your own residential pool). Used as the ``proxies=`` arg on
  ``httpx`` and as the ``proxy=`` arg on Playwright contexts.

Both are optional. If neither env var is set we fall back to a direct
``httpx.Client`` with the configured user agent — which is fine for Shopify
endpoints that don't gate by IP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

from ..config import get_settings


@dataclass
class ProxyConfig:
    scraperapi_key: Optional[str] = None
    proxy_url: Optional[str] = None  # http://user:pass@host:port
    render_js_default: bool = False
    scraperapi_premium: bool = False
    scraperapi_ultra_premium: bool = False

    @classmethod
    def from_env(cls) -> "ProxyConfig":
        # Use app Settings (loads backend/.env) so uvicorn runs pick up keys.
        s = get_settings()
        return cls(
            scraperapi_key=s.scraperapi_key or None,
            proxy_url=s.scraper_proxy_url or None,
            render_js_default=bool(s.scraper_render_js),
            scraperapi_premium=bool(s.scraperapi_premium),
            scraperapi_ultra_premium=bool(s.scraperapi_ultra_premium),
        )

    @property
    def has_provider(self) -> bool:
        return bool(self.scraperapi_key or self.proxy_url)


def wrap_url_for_scraperapi(url: str, key: str, *, render_js: bool, country: str | None = None) -> str:
    """Wrap a URL for ScraperAPI (https://www.scraperapi.com/).

    Free trial: 5,000 credits / 7 days, then 1,000 credits/month free, no card.
    Sign up → dashboard → copy API key → set ``SCRAPERAPI_KEY`` in ``backend/.env``.
    """
    cfg = ProxyConfig.from_env()
    qs = {"api_key": key, "url": url, "render": "true" if render_js else "false", "keep_headers": "true"}
    if cfg.scraperapi_ultra_premium:
        qs["ultra_premium"] = "true"
    elif cfg.scraperapi_premium:
        qs["premium"] = "true"
    if country:
        qs["country_code"] = country
    return f"http://api.scraperapi.com/?{urlencode(qs)}"


def get_text_via_provider(
    url: str,
    *,
    timeout: float = 30.0,
    user_agent: str = "CompetitorWatchBot/0.1",
    render_js: bool | None = None,
    country: str | None = None,
) -> str:
    """Fetch ``url`` honoring whichever provider is configured.

    Order of preference: ScraperAPI > generic proxy > direct.
    Raises ``httpx.HTTPStatusError`` on 4xx/5xx (after letting tenacity at the
    caller layer retry transient ones).
    """
    cfg = ProxyConfig.from_env()
    render = cfg.render_js_default if render_js is None else render_js
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/json,*/*"}

    if cfg.scraperapi_key:
        target = wrap_url_for_scraperapi(url, cfg.scraperapi_key, render_js=render, country=country)
        logger.info("scrape via ScraperAPI render=%s country=%s url=%s", render, country, url)
        with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
            r = client.get(target)
            r.raise_for_status()
            return r.text

    if cfg.proxy_url:
        logger.info("scrape via proxy=%s url=%s", cfg.proxy_url.split("@")[-1], url)
        with httpx.Client(
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
            proxy=cfg.proxy_url,
            verify=True,
        ) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text

    logger.info("scrape direct url=%s", url)
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def get_json_via_provider(url: str, **kwargs) -> dict:
    text = get_text_via_provider(url, **kwargs)
    import json
    return json.loads(text)
