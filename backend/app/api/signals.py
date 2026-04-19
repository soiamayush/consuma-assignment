from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import BlogPost, Competitor, Product, Signal
from ..schemas import BlogPostOut, DashboardSummary, SignalOut
from ..time_utils import utc_now

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/signals", response_model=list[SignalOut])
def list_signals(
    response: Response,
    competitor: Optional[str] = None,
    kind: Optional[str] = None,
    theme: Optional[str] = None,
    window_days: int = Query(30, ge=1, le=365),
    sort: str = Query("importance", pattern="^(importance|recent)$"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    since = utc_now() - timedelta(days=window_days)
    base = select(Signal).where(Signal.created_at >= since)
    if competitor:
        base = base.join(Competitor).where(Competitor.slug == competitor)
    if kind:
        base = base.where(Signal.kind == kind)

    # `theme` is a JSON list filter; we approximate the count without it (cheap)
    # and then refine the page in Python — filtered totals would require a JSON
    # contains operator we cannot rely on across SQLite/Postgres.
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    page = base.options(selectinload(Signal.competitor))
    if sort == "importance":
        page = page.order_by(Signal.importance.desc(), Signal.created_at.desc())
    else:
        page = page.order_by(Signal.created_at.desc())

    if theme:
        page = page.offset(offset).limit(limit * 4)
        results = [s for s in db.scalars(page) if theme in (s.themes or [])][:limit]
    else:
        page = page.offset(offset).limit(limit)
        results = list(db.scalars(page))

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    return [
        SignalOut(
            id=s.id,
            competitor_id=s.competitor_id,
            competitor_name=s.competitor.name if s.competitor else None,
            competitor_slug=s.competitor.slug if s.competitor else None,
            kind=s.kind,
            entity_type=s.entity_type,
            entity_id=s.entity_id,
            title=s.title,
            description=s.description,
            delta=s.delta or {},
            themes=s.themes or [],
            importance=s.importance,
            created_at=s.created_at,
        )
        for s in results
    ]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    window_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    since = utc_now() - timedelta(days=window_days)

    total = db.scalar(select(func.count(Signal.id)).where(Signal.created_at >= since)) or 0

    def count_kind(k: str) -> int:
        return db.scalar(
            select(func.count(Signal.id)).where(Signal.created_at >= since, Signal.kind == k)
        ) or 0

    new_products = count_kind("PRODUCT_LAUNCH")
    price_drops = count_kind("PRICE_DROP")
    price_increases = count_kind("PRICE_INCREASE")
    blog_posts = count_kind("BLOG_POST")

    # Top themes: scan signals in window and tally.
    sigs = list(db.scalars(select(Signal).where(Signal.created_at >= since)))
    theme_counts: dict[str, int] = {}
    for s in sigs:
        for t in s.themes or []:
            theme_counts[t] = theme_counts.get(t, 0) + 1
    top_themes = sorted(
        [{"theme": t, "count": c} for t, c in theme_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:8]

    # Aggregate per-competitor signal stats in the window; include brands with 0.
    comps = list(db.scalars(select(Competitor)))
    by_competitor: list[dict] = []
    for c in comps:
        cnt = db.scalar(
            select(func.count(Signal.id)).where(
                Signal.competitor_id == c.id, Signal.created_at >= since
            )
        ) or 0
        top_imp = db.scalar(
            select(func.max(Signal.importance)).where(
                Signal.competitor_id == c.id, Signal.created_at >= since
            )
        ) or 0.0
        by_competitor.append(
            {"slug": c.slug, "name": c.name, "signal_count": cnt, "top_importance": float(top_imp)}
        )
    by_competitor.sort(key=lambda x: x["signal_count"], reverse=True)

    return DashboardSummary(
        window_days=window_days,
        total_signals=total,
        new_products=new_products,
        price_drops=price_drops,
        price_increases=price_increases,
        blog_posts=blog_posts,
        top_themes=top_themes,
        by_competitor=by_competitor,
    )


@router.get("/blog-posts", response_model=list[BlogPostOut])
def list_blog_posts(
    competitor: Optional[str] = None,
    limit: int = Query(30, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(BlogPost).options(selectinload(BlogPost.competitor))
    if competitor:
        stmt = stmt.join(Competitor).where(Competitor.slug == competitor)
    # SQLite treats NULL as the smallest value in ASC; in DESC NULLs come first.
    # Using coalesce with first_seen_at gives us sane ordering regardless of backend.
    from sqlalchemy import func as sa_func
    stmt = stmt.order_by(sa_func.coalesce(BlogPost.published_at, BlogPost.first_seen_at).desc()).limit(limit)
    posts = list(db.scalars(stmt))
    return [
        BlogPostOut(
            id=p.id,
            competitor_id=p.competitor_id,
            competitor_name=p.competitor.name if p.competitor else None,
            title=p.title,
            url=p.url,
            summary=p.summary,
            published_at=p.published_at,
            first_seen_at=p.first_seen_at,
        )
        for p in posts
    ]
