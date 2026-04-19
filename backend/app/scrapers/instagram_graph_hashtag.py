"""Instagram Graph API — hashtag media (official Meta API only).

There is **no** supported way to scrape ``instagram.com`` HTML at scale; Meta
blocks it and it violates their Terms. What professional stacks use instead is
the **Instagram Graph API**: resolve a hashtag id, then read ``top_media`` and
``recent_media`` for public posts (subject to Meta permissions and rate caps).

Requirements (set in ``backend/.env``):

- ``INSTAGRAM_ACCESS_TOKEN`` — a long‑lived **User** or **Page** access token that
  includes the Instagram permissions your app was granted (typical combo:
  ``instagram_basic``, ``pages_read_engagement``; hashtag search may require
  **Instagram Public Content** / advanced access — see Meta's App Review docs).
- ``INSTAGRAM_GRAPH_USER_ID`` — the **Instagram professional** (Business or
  Creator) account **id** (numeric string) that is linked to your Meta app and
  used as the ``user_id`` parameter on hashtag endpoints. This is *not* your
  Facebook Page id; find it in Graph API Explorer or the ``/me`` / connected
  accounts flows.

If either value is missing, this source **yields nothing** and does not error,
so the rest of ingestion keeps working.

Config (per ``Source`` row):

    hashtag: str   — without ``#``, e.g. ``mamaearth`` (letters, numbers, underscore)

Caveats (Meta-imposed):

- ``recent_media`` is largely **last 24 hours** of posts for that hashtag.
- ``top_media`` surfaces **popular** posts (better for slower-moving tags).
- Hashtag volume is **capped** (on the order of tens of unique tags per week per
  app) — we only query **one** tag per brand per run.
- Returned objects may omit ``like_count`` / ``username`` unless your app has
  the right permissions; we degrade gracefully.

API reference:
    https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag-search
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from ..config import get_settings
from .base import BaseSource, FetchContext, RawSocialMention

logger = logging.getLogger(__name__)

_GRAPH = "https://graph.facebook.com/v19.0"


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith("+0000"):
            s = s[:-5] + "Z"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _owner_username(item: dict[str, Any]) -> str | None:
    owner = item.get("owner")
    if isinstance(owner, dict):
        u = owner.get("username")
        if u:
            return str(u)
    u = item.get("username")
    return str(u) if u else None


class InstagramGraphHashtagSource(BaseSource):
    kind = "instagram_graph_hashtag"

    def fetch_social_mentions(self, ctx: FetchContext) -> Iterable[RawSocialMention]:
        settings = get_settings()
        token = (settings.instagram_access_token or "").strip()
        ig_user_id = (settings.instagram_graph_user_id or "").strip()
        if not token or not ig_user_id:
            logger.info(
                "instagram_graph_hashtag: set INSTAGRAM_ACCESS_TOKEN and "
                "INSTAGRAM_GRAPH_USER_ID in backend/.env to enable (skipping)."
            )
            return []

        cfg = self.config or {}
        tag = (cfg.get("hashtag") or "").strip().lstrip("#").lower()
        if not tag or not tag.replace("_", "").isalnum():
            logger.warning("instagram_graph_hashtag: invalid or empty `hashtag` in config; skipping.")
            return []

        params_base: dict[str, str] = {"access_token": token}
        headers = {"User-Agent": ctx.user_agent}

        def get_json(path: str, extra: dict[str, str]) -> dict[str, Any]:
            with httpx.Client(timeout=ctx.timeout, headers=headers) as client:
                r = client.get(f"{_GRAPH}{path}", params={**params_base, **extra})
                try:
                    return r.json()
                except ValueError:
                    return {"error": {"message": r.text[:200], "code": r.status_code}}

        # --- resolve hashtag id -------------------------------------------------
        res = get_json(
            "/ig_hashtag_search",
            {"user_id": ig_user_id, "q": tag},
        )
        err = res.get("error")
        if err:
            logger.warning(
                "instagram_graph_hashtag: hashtag search failed for #%s: %s",
                tag,
                err.get("message", err),
            )
            return []
        data = res.get("data") or []
        if not data or not data[0].get("id"):
            return []
        hashtag_id = str(data[0]["id"])

        # Try rich fields first; fall back if ``owner`` is not permitted.
        fields_primary = (
            "id,media_type,permalink,caption,timestamp,like_count,comments_count,owner{username}"
        )
        fields_fallback = "id,media_type,permalink,caption,timestamp,like_count,comments_count"

        collected: dict[str, dict[str, Any]] = {}
        for edge in ("top_media", "recent_media"):
            payload = get_json(
                f"/{hashtag_id}/{edge}",
                {
                    "user_id": ig_user_id,
                    "fields": fields_primary,
                    "limit": "25",
                },
            )
            if payload.get("error") and "owner" in str(payload.get("error", {}).get("message", "")).lower():
                payload = get_json(
                    f"/{hashtag_id}/{edge}",
                    {
                        "user_id": ig_user_id,
                        "fields": fields_fallback,
                        "limit": "25",
                    },
                )
            if payload.get("error"):
                logger.warning(
                    "instagram_graph_hashtag: %s for #%s failed: %s",
                    edge,
                    tag,
                    payload["error"].get("message", payload["error"]),
                )
                continue
            for item in payload.get("data") or []:
                mid = item.get("id")
                if mid:
                    collected[str(mid)] = item

        out: list[RawSocialMention] = []
        for mid, item in collected.items():
            permalink = (item.get("permalink") or "").strip()
            if not permalink:
                continue
            cap = (item.get("caption") or "").strip()
            title = (cap[:120] + "…") if len(cap) > 120 else (cap or f"Instagram {item.get('media_type', 'post')}")
            user = _owner_username(item)
            likes = item.get("like_count")
            comments = item.get("comments_count")
            try:
                likes_i = int(likes) if likes is not None else None
            except (TypeError, ValueError):
                likes_i = None
            try:
                comments_i = int(comments) if comments is not None else None
            except (TypeError, ValueError):
                comments_i = None

            out.append(
                RawSocialMention(
                    external_id=mid,
                    platform="instagram",
                    url=permalink,
                    title=title,
                    summary=cap[:500] if cap else None,
                    author=user or f"#{tag}",
                    author_handle=user or f"#{tag}",
                    author_url=(
                        f"https://www.instagram.com/{user}/"
                        if user
                        else f"https://www.instagram.com/explore/tags/{tag}/"
                    ),
                    thumbnail_url=None,
                    metric_views=None,
                    metric_score=likes_i,
                    metric_comments=comments_i,
                    published_at=_parse_ts(item.get("timestamp")),
                    raw={"hashtag": tag, "media_type": item.get("media_type")},
                )
            )
        return out
