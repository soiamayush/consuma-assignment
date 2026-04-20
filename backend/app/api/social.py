"""Social/buzz API: paged mentions and top voices per brand.

Backed by ``SocialMention`` rows from YouTube, Google News, Bing News, Apple
Podcasts search, and optionally Instagram Graph (hashtag) when configured.
Only **read-only** GET endpoints; ingestion is owned by the runner.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Competitor, SocialMention
from ..schemas import SocialMentionOut, TopCreatorOut
from ..time_utils import utc_now

router = APIRouter(prefix="/api/social", tags=["social"])

VALID_PLATFORMS = ("youtube", "news", "news_bing", "podcast", "instagram", "reddit")
VALID_SORTS = ("recent", "views", "score")


def _serialize(m: SocialMention) -> SocialMentionOut:
    return SocialMentionOut(
        id=m.id,
        competitor_id=m.competitor_id,
        competitor_name=m.competitor.name if m.competitor else None,
        competitor_slug=m.competitor.slug if m.competitor else None,
        platform=m.platform,
        external_id=m.external_id,
        url=m.url,
        title=m.title,
        summary=m.summary,
        author=m.author,
        author_handle=m.author_handle,
        author_url=m.author_url,
        thumbnail_url=m.thumbnail_url,
        metric_views=m.metric_views,
        metric_score=m.metric_score,
        metric_comments=m.metric_comments,
        published_at=m.published_at,
        first_seen_at=m.first_seen_at,
    )


@router.get("", response_model=list[SocialMentionOut])
def list_mentions(
    response: Response,
    competitor: Optional[str] = None,
    platform: Optional[str] = Query(None, description="youtube|news|news_bing|podcast|instagram"),
    window_days: int = Query(90, ge=1, le=365),
    sort: str = Query("recent", description="recent|views|score"),
    limit: int = Query(25, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if platform and platform not in VALID_PLATFORMS:
        platform = None
    if sort not in VALID_SORTS:
        sort = "recent"

    since = utc_now() - timedelta(days=window_days)
    # Use COALESCE so mentions with no published_at still appear (fall back to first_seen_at).
    seen_at = func.coalesce(SocialMention.published_at, SocialMention.first_seen_at)
    base = select(SocialMention).where(seen_at >= since)
    if competitor:
        base = base.join(Competitor).where(Competitor.slug == competitor)
    if platform:
        base = base.where(SocialMention.platform == platform)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    page = base.options(selectinload(SocialMention.competitor))
    if sort == "views":
        # YouTube uses ``metric_views``; Instagram stores likes on ``metric_score``.
        reach = func.coalesce(SocialMention.metric_views, SocialMention.metric_score)
        page = page.order_by(reach.desc().nulls_last(), seen_at.desc())
    elif sort == "score":
        page = page.order_by(SocialMention.metric_score.desc().nulls_last(), seen_at.desc())
    else:
        page = page.order_by(seen_at.desc())
    page = page.offset(offset).limit(limit)

    rows = list(db.scalars(page))
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [_serialize(m) for m in rows]


@router.get("/creators", response_model=list[TopCreatorOut])
def top_creators(
    competitor: Optional[str] = None,
    platform: str = Query("youtube", description="youtube|news|news_bing|podcast|instagram"),
    window_days: int = Query(90, ge=1, le=365),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Top promoters / outlets for a brand on a given platform.

    For YouTube: aggregated by channel with summed views.
    For news (Google or Bing): aggregated by publication name.
    For podcasts: aggregated by show name (``collectionName``).
    For Instagram: aggregated by poster ``username`` when present, else hashtag.
    """
    if platform not in VALID_PLATFORMS:
        platform = "youtube"

    since = utc_now() - timedelta(days=window_days)
    seen_at = func.coalesce(SocialMention.published_at, SocialMention.first_seen_at)

    stmt = (
        select(
            Competitor.slug,
            Competitor.name,
            SocialMention.platform,
            SocialMention.author,
            SocialMention.author_handle,
            SocialMention.author_url,
            func.count(SocialMention.id).label("mention_count"),
            func.coalesce(func.sum(SocialMention.metric_views), 0).label("total_views"),
            func.coalesce(func.sum(SocialMention.metric_score), 0).label("total_score"),
            func.max(SocialMention.url).label("sample_url"),
        )
        .join(Competitor, Competitor.id == SocialMention.competitor_id)
        .where(SocialMention.platform == platform, seen_at >= since, SocialMention.author.isnot(None))
        .group_by(
            Competitor.slug,
            Competitor.name,
            SocialMention.platform,
            SocialMention.author,
            SocialMention.author_handle,
            SocialMention.author_url,
        )
    )
    if competitor:
        stmt = stmt.where(Competitor.slug == competitor)
    # Rank by reach (views) when present, else mention count.
    stmt = stmt.order_by(
        case(
            (func.coalesce(func.sum(SocialMention.metric_views), 0) > 0, func.coalesce(func.sum(SocialMention.metric_views), 0)),
            else_=func.count(SocialMention.id),
        ).desc(),
        func.count(SocialMention.id).desc(),
    ).limit(limit)

    out: list[TopCreatorOut] = []
    for row in db.execute(stmt):
        out.append(
            TopCreatorOut(
                competitor_slug=row.slug,
                competitor_name=row.name,
                platform=row.platform,
                author=row.author,
                author_handle=row.author_handle,
                author_url=row.author_url,
                mention_count=int(row.mention_count or 0),
                total_views=int(row.total_views) if row.total_views else None,
                total_score=int(row.total_score) if row.total_score else None,
                sample_url=row.sample_url,
            )
        )
    return out


@router.get("/summary")
def summary(
    window_days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Per-brand × per-platform mention counts for a quick at-a-glance buzz table."""
    since = utc_now() - timedelta(days=window_days)
    seen_at = func.coalesce(SocialMention.published_at, SocialMention.first_seen_at)

    rows = db.execute(
        select(
            Competitor.slug,
            Competitor.name,
            Competitor.is_anchor,
            SocialMention.platform,
            func.count(SocialMention.id).label("n"),
            func.coalesce(func.sum(SocialMention.metric_views), 0).label("views"),
        )
        .join(Competitor, Competitor.id == SocialMention.competitor_id)
        .where(seen_at >= since)
        .group_by(Competitor.slug, Competitor.name, Competitor.is_anchor, SocialMention.platform)
    ).all()

    by_brand: dict[str, dict[str, Any]] = {}
    for r in rows:
        b = by_brand.setdefault(
            r.slug,
            {"slug": r.slug, "name": r.name, "is_anchor": bool(r.is_anchor), "platforms": {}, "total": 0, "views": 0},
        )
        b["platforms"][r.platform] = {"mentions": int(r.n), "views": int(r.views or 0)}
        b["total"] += int(r.n)
        b["views"] += int(r.views or 0)

    return {
        "window_days": window_days,
        "by_brand": sorted(by_brand.values(), key=lambda x: (x["total"], x["views"]), reverse=True),
    }
