"""YouTube Data API v3 search source.

Each ingestion run searches for the brand on YouTube, picks up to ``max_results``
videos published in the last ``window_days`` days, then enriches them with
view/like/comment counts via ``videos.list``. Results are emitted as
``RawSocialMention`` records the runner upserts into ``social_mentions``.

Config:
    query: str           — exact YouTube search query (defaults to brand name)
    window_days: int     — only videos published after now-N days (default 90)
    max_results: int     — search.list page size (default 25, max 50)
    region_code: str     — ISO country code, e.g. "IN" (optional)
    relevance_language: str — e.g. "en" (optional)

Quota cost per run: 100 (search) + 1 (videos.list batch) ≈ 101 units. Free daily
quota is 10 000 units, so ~99 runs/day is safe.

If ``YOUTUBE_API_KEY`` is missing, the scraper logs a warning and yields nothing
(does NOT raise) so the rest of the pipeline keeps running.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

import httpx

from ..config import get_settings
from .base import BaseSource, FetchContext, RawSocialMention

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeSearchSource(BaseSource):
    kind = "youtube_search"

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:
        api_key = get_settings().youtube_api_key
        if not api_key:
            logger.warning(
                "youtube_search: YOUTUBE_API_KEY not set in backend/.env; skipping (no error)."
            )
            return []

        cfg = self.config or {}
        query = (cfg.get("query") or "").strip()
        if not query:
            logger.warning("youtube_search: empty `query` config; skipping.")
            return []

        window_days = int(cfg.get("window_days", 90))
        max_results = max(1, min(int(cfg.get("max_results", 25)), 50))
        region_code = cfg.get("region_code")
        rel_lang = cfg.get("relevance_language")

        published_after = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        params: dict[str, str | int] = {
            "key": api_key,
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": "relevance",
            "publishedAfter": published_after,
        }
        if region_code:
            params["regionCode"] = region_code
        if rel_lang:
            params["relevanceLanguage"] = rel_lang

        try:
            with httpx.Client(timeout=ctx.timeout, headers={"User-Agent": ctx.user_agent}) as client:
                search_resp = client.get(_SEARCH_URL, params=params)
                if search_resp.status_code == 403:
                    logger.warning(
                        "youtube_search: 403 (quota exceeded or key restricted) for query=%r", query
                    )
                    return []
                search_resp.raise_for_status()
                items = search_resp.json().get("items", []) or []
                video_ids = [
                    it.get("id", {}).get("videoId")
                    for it in items
                    if it.get("id", {}).get("videoId")
                ]
                if not video_ids:
                    return []

                # Enrich with statistics in a single videos.list call.
                vresp = client.get(
                    _VIDEOS_URL,
                    params={
                        "key": api_key,
                        "part": "snippet,statistics",
                        "id": ",".join(video_ids),
                        "maxResults": 50,
                    },
                )
                vresp.raise_for_status()
                vmap = {v.get("id"): v for v in (vresp.json().get("items") or [])}
        except httpx.HTTPError as exc:
            logger.warning("youtube_search request failed: %s", exc)
            return []

        out: list[RawSocialMention] = []
        for vid in video_ids:
            v = vmap.get(vid)
            if not v:
                continue
            sn = v.get("snippet", {}) or {}
            stats = v.get("statistics", {}) or {}
            published = sn.get("publishedAt")
            try:
                published_dt = (
                    datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
                )
            except ValueError:
                published_dt = None
            thumb = (sn.get("thumbnails") or {}).get("medium") or (sn.get("thumbnails") or {}).get("default") or {}
            channel_id = sn.get("channelId")
            out.append(
                RawSocialMention(
                    external_id=vid,
                    platform="youtube",
                    url=f"https://www.youtube.com/watch?v={vid}",
                    title=sn.get("title") or "(untitled)",
                    summary=(sn.get("description") or "").strip()[:500] or None,
                    author=sn.get("channelTitle"),
                    author_handle=channel_id,
                    author_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
                    thumbnail_url=thumb.get("url"),
                    metric_views=_to_int(stats.get("viewCount")),
                    metric_score=_to_int(stats.get("likeCount")),
                    metric_comments=_to_int(stats.get("commentCount")),
                    published_at=published_dt,
                    raw={"snippet": sn, "statistics": stats},
                )
            )
        return out


def _to_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
