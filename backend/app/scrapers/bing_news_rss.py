"""Bing News RSS source (second news corpus, no API key).

Professional listening stacks often blend **multiple news indexes** so blind
spots from one aggregator don't dominate the narrative. This hits Microsoft's
public RSS endpoint — same shape as ``news_rss.py`` but different publishers.

Config:
    query: str        — search terms
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


class BingNewsRssSource(BaseSource):
    kind = "bing_news_rss"

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:
        cfg = self.config or {}
        query = (cfg.get("query") or "").strip()
        if not query:
            logger.warning("bing_news_rss: empty `query` config; skipping.")
            return []

        max_items = max(1, int(cfg.get("max_items", 25)))
        url = f"https://www.bing.com/news/search?q={quote(query)}&format=rss"

        try:
            with httpx.Client(timeout=ctx.timeout, headers={"User-Agent": ctx.user_agent}) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
                xml = resp.text
        except httpx.HTTPError as exc:
            logger.warning("bing_news_rss request failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            logger.warning("bing_news_rss XML parse failed: %s", exc)
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
            try:
                published_dt = parsedate_to_datetime(pub) if pub else None
            except (TypeError, ValueError):
                published_dt = None

            source_name = None
            source_href = None
            for child in it:
                if child.tag.endswith("Source") or child.tag == "Source":
                    source_name = (child.text or "").strip() or None
                    source_href = child.get("url")
                    break
            if not source_name:
                source_name = urlparse(link).hostname

            out.append(
                RawSocialMention(
                    external_id=guid[:255],
                    platform="news_bing",
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
                    raw={"engine": "bing_news"},
                )
            )
        return out


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s).strip()
