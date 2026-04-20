"""Reddit search RSS/Atom source (public, no API key).

Reddit exposes a lightweight feed endpoint that returns Atom for search queries:
    https://www.reddit.com/search.rss?q=<query>&sort=new&t=<time>

We treat each post as a ``RawSocialMention`` with platform="reddit".

Config:
    query: str        — search terms (required)
    sort: str         — new|hot|top|relevance (default "new")
    t: str            — hour|day|week|month|year|all (default "week")
    max_items: int    — cap (default 25)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import quote
from xml.etree import ElementTree as ET

import httpx

from .base import BaseSource, FetchContext, RawSocialMention

logger = logging.getLogger(__name__)


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s).strip()


def _child_text(el: ET.Element, local_name: str) -> str | None:
    """Find first child whose tag ends with `local_name` (namespace-safe)."""
    for ch in list(el):
        if ch.tag == local_name or ch.tag.endswith(f"}}{local_name}"):
            txt = (ch.text or "").strip()
            return txt or None
    return None


def _child_attr(el: ET.Element, local_name: str, attr: str) -> str | None:
    for ch in list(el):
        if ch.tag == local_name or ch.tag.endswith(f"}}{local_name}"):
            v = (ch.get(attr) or "").strip()
            return v or None
    return None


class RedditSearchRssSource(BaseSource):
    kind = "reddit_search_rss"

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:
        cfg = self.config or {}
        query = (cfg.get("query") or "").strip()
        if not query:
            logger.warning("reddit_search_rss: empty `query` config; skipping.")
            return []

        sort = (cfg.get("sort") or "new").strip()
        t = (cfg.get("t") or "week").strip()
        max_items = max(1, int(cfg.get("max_items", 25)))

        url = f"https://www.reddit.com/search.rss?q={quote(query)}&sort={quote(sort)}&t={quote(t)}"

        try:
            with httpx.Client(timeout=ctx.timeout, headers={"User-Agent": ctx.user_agent}) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
                xml = resp.text
        except httpx.HTTPError as exc:
            logger.warning("reddit_search_rss request failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            logger.warning("reddit_search_rss XML parse failed: %s", exc)
            return []

        # Reddit serves Atom for /search.rss (root tag typically "{...}feed").
        entries: list[ET.Element] = []
        if root.tag.endswith("feed"):
            entries = root.findall(".//{*}entry")
        else:
            entries = root.findall(".//item")

        out: list[RawSocialMention] = []
        for ent in entries[:max_items]:
            title = (_child_text(ent, "title") or "").strip()
            link = (_child_attr(ent, "link", "href") or _child_text(ent, "link") or "").strip()
            guid = (_child_text(ent, "id") or _child_text(ent, "guid") or link).strip()
            if not title or not link or not guid:
                continue

            # Atom: <content type="html">, RSS: <description>
            content_html = _child_text(ent, "content") or _child_text(ent, "description") or ""
            summary = _strip_html(content_html)[:500] or None

            author = _child_text(ent, "name") or _child_text(ent, "author") or _child_text(ent, "dc:creator")
            author_url = _child_attr(ent, "author", "href")

            published_dt: datetime | None = None
            published_raw = _child_text(ent, "updated") or _child_text(ent, "published") or _child_text(ent, "pubDate")
            if published_raw:
                # Atom is ISO-8601; RSS is RFC-2822.
                try:
                    published_dt = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        published_dt = parsedate_to_datetime(published_raw)
                    except (TypeError, ValueError):
                        published_dt = None

            out.append(
                RawSocialMention(
                    external_id=guid[:255],
                    platform="reddit",
                    url=link,
                    title=title[:500],
                    summary=summary,
                    author=author,
                    author_handle=None,
                    author_url=author_url,
                    thumbnail_url=None,
                    metric_views=None,
                    metric_score=None,
                    metric_comments=None,
                    published_at=published_dt,
                    raw={"query": query, "sort": sort, "t": t},
                )
            )

        return out

