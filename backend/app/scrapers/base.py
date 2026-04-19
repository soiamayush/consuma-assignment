"""Source abstraction.

Each concrete source knows how to fetch + parse a particular kind of public endpoint.
The ingestion runner doesn't care what the source is; it only consumes normalized
`RawProduct` / `RawBlogPost` records.

Design notes:
- Fetch is separate from parse so we can unit-test parsers against fixtures.
- Sources handle their own pagination and yield items lazily.
- Retries are done at the HTTP layer with exponential backoff.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

import httpx
from urllib.parse import urlparse
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class RawProduct:
    external_id: str
    handle: Optional[str]
    title: str
    product_type: Optional[str]
    vendor: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    tags: list[str]
    price_min: Optional[float]
    price_max: Optional[float]
    currency: Optional[str]
    available: bool
    variants_count: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawBlogPost:
    external_id: str
    url: str
    title: str
    summary: Optional[str]
    published_at: Optional[datetime]


@dataclass
class RawSocialMention:
    """A normalised buzz item (YouTube, news, podcasts, Instagram, …)."""

    external_id: str
    platform: str  # e.g. youtube | news | news_bing | podcast | instagram
    url: str
    title: str
    summary: Optional[str] = None
    author: Optional[str] = None
    author_handle: Optional[str] = None
    author_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    metric_views: Optional[int] = None
    metric_score: Optional[int] = None
    metric_comments: Optional[int] = None
    published_at: Optional[datetime] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchContext:
    user_agent: str
    timeout: float
    max_pages: int


class SourceError(Exception):
    pass


class BaseSource(abc.ABC):
    """Abstract scraping source."""

    kind: str = "base"

    def __init__(self, url: str, config: dict[str, Any] | None = None) -> None:
        self.url = url
        self.config = config or {}

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:  # pragma: no cover - default
        return []

    def fetch_blog_posts(self, ctx: FetchContext) -> Iterable[RawBlogPost]:  # pragma: no cover - default
        return []

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:  # pragma: no cover - default
        return []


# ---- HTTP helper with retries -------------------------------------------------


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def http_get_json(url: str, ctx: FetchContext) -> dict[str, Any]:
    headers = {"User-Agent": ctx.user_agent, "Accept": "application/json"}
    with httpx.Client(timeout=ctx.timeout, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        # Treat 429/5xx as retryable
        if resp.status_code >= 500 or resp.status_code == 429:
            raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            # Some stores return HTML blocks/CAPTCHA with 200. If a scraping provider is
            # configured, retry via provider to get real JSON.
            from .proxy import get_json_via_provider
            host = (urlparse(url).hostname or "").lower()
            country = "in" if host.endswith(".in") else None
            return get_json_via_provider(
                url, timeout=ctx.timeout, user_agent=ctx.user_agent, render_js=False, country=country
            )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def http_get_text(url: str, ctx: FetchContext) -> str:
    headers = {"User-Agent": ctx.user_agent}
    with httpx.Client(timeout=ctx.timeout, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        if resp.status_code >= 500 or resp.status_code == 429:
            raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
        resp.raise_for_status()
        text = resp.text
        if not text or text.lstrip().startswith("<!DOCTYPE html") or text.lstrip().startswith("<html"):
            # If a provider is configured, prefer it for HTML-gated pages.
            from .proxy import get_text_via_provider

            return get_text_via_provider(url, timeout=ctx.timeout, user_agent=ctx.user_agent, render_js=True)
        return text
