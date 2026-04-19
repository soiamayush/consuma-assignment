"""Apple iTunes / Podcasts search (public JSON, no API key).

Enterprise social-listening products almost always include **podcast audio**
because sponsorship and creator endorsements show up there first. Apple's
lookup endpoint is free, unauthenticated, and stable enough for a prototype.

Config:
    query: str       — search terms (brand + category wording)
    country: str     — ISO store country (default "in")
    limit: int       — max results 1..200 (default 25)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import quote

import httpx

from .base import BaseSource, FetchContext, RawSocialMention

logger = logging.getLogger(__name__)

_LOOKUP = "https://itunes.apple.com/search"


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # e.g. "2024-03-15T12:00:00Z"
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class ItunesPodcastSource(BaseSource):
    kind = "itunes_podcast"

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:
        cfg = self.config or {}
        query = (cfg.get("query") or "").strip()
        if not query:
            logger.warning("itunes_podcast: empty `query` config; skipping.")
            return []

        country = (cfg.get("country") or "in").lower()
        limit = max(1, min(int(cfg.get("limit", 25)), 200))

        url = (
            f"{_LOOKUP}?term={quote(query)}&entity=podcastEpisode&limit={limit}&country={quote(country)}"
        )

        try:
            with httpx.Client(timeout=ctx.timeout, headers={"User-Agent": ctx.user_agent}) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("itunes_podcast request failed: %s", exc)
            return []

        results: list[dict[str, Any]] = data.get("results") or []
        out: list[RawSocialMention] = []
        for row in results:
            tid = row.get("trackId")
            if tid is None:
                continue
            ext = str(tid)
            title = (row.get("trackName") or "").strip() or "(untitled episode)"
            show = (row.get("collectionName") or "").strip() or None
            artist = (row.get("artistName") or "").strip() or None
            episode_url = (row.get("trackViewUrl") or "").strip()
            if not episode_url:
                continue
            thumb = row.get("artworkUrl600") or row.get("artworkUrl160")
            summary = (row.get("shortDescription") or row.get("description") or "").strip()
            if summary:
                summary = summary[:500]
            else:
                summary = None
            published = _parse_date(row.get("releaseDate"))
            # Normalize to naive UTC for DB consistency with other scrapers.
            pub_naive = None
            if published and published.tzinfo:
                pub_naive = published.astimezone(timezone.utc).replace(tzinfo=None)
            elif published:
                pub_naive = published

            out.append(
                RawSocialMention(
                    external_id=ext,
                    platform="podcast",
                    url=episode_url,
                    title=f"{show}: {title}" if show else title,
                    summary=summary,
                    author=show or artist,
                    author_handle=artist,
                    author_url=row.get("feedUrl"),
                    thumbnail_url=thumb,
                    metric_views=None,
                    metric_score=None,
                    metric_comments=None,
                    published_at=pub_naive,
                    raw={
                        "collectionId": row.get("collectionId"),
                        "trackTimeMillis": row.get("trackTimeMillis"),
                    },
                )
            )
        return out
