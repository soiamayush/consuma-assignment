"""Google News RSS source.

Free, no key. Builds an RSS URL from the configured query, parses it, and
emits one ``RawSocialMention`` per article.

Config:
    query: str        — search terms (defaults to brand name)
    hl: str           — UI language (default "en-IN")
    gl: str           — country (default "IN")
    ceid: str         — combined region:lang (default "IN:en")
    max_items: int    — cap (default 25)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import httpx

from .base import BaseSource, FetchContext, RawSocialMention

logger = logging.getLogger(__name__)


class NewsRssSource(BaseSource):
    kind = "news_rss"

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:
        cfg = self.config or {}
        query = (cfg.get("query") or "").strip()
        if not query:
            logger.warning("news_rss: empty `query` config; skipping.")
            return []

        hl = cfg.get("hl", "en-IN")
        gl = cfg.get("gl", "IN")
        ceid = cfg.get("ceid", "IN:en")
        max_items = max(1, int(cfg.get("max_items", 25)))

        url = (
            "https://news.google.com/rss/search"
            f"?q={quote(query)}&hl={quote(hl)}&gl={quote(gl)}&ceid={quote(ceid)}"
        )

        try:
            with httpx.Client(timeout=ctx.timeout, headers={"User-Agent": ctx.user_agent}) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
                xml = resp.text
        except httpx.HTTPError as exc:
            logger.warning("news_rss request failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            logger.warning("news_rss XML parse failed: %s", exc)
            return []

        items = root.findall(".//item")[:max_items]
        out: list[RawSocialMention] = []
        for it in items:
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if not title or not link:
                continue
            guid = (it.findtext("guid") or link).strip()
            desc_html = (it.findtext("description") or "").strip()
            summary = _strip_html(desc_html)[:500] or None
            pub = it.findtext("pubDate")
            published_dt: datetime | None
            try:
                published_dt = parsedate_to_datetime(pub) if pub else None
            except (TypeError, ValueError):
                published_dt = None
            source_el = it.find("source")
            source_name = source_el.text if source_el is not None else None
            source_href = source_el.get("url") if source_el is not None else None
            if not source_name and link:
                source_name = urlparse(link).hostname

            out.append(
                RawSocialMention(
                    external_id=guid,
                    platform="news",
                    url=link,
                    title=title,
                    summary=summary,
                    author=source_name,
                    author_handle=urlparse(source_href).hostname if source_href else None,
                    author_url=source_href,
                    thumbnail_url=None,
                    metric_views=None,
                    metric_score=None,
                    metric_comments=None,
                    published_at=published_dt,
                    raw={"description_html": desc_html},
                )
            )
        return out


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s).strip()
