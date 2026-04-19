from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BlogPost, Competitor, IngestionRun, Product, Signal, Source
from ..schemas import CompetitorDetail

router = APIRouter(prefix="/api/competitors", tags=["competitors"])


def _competitor_detail(db: Session, c: Competitor) -> CompetitorDetail:
    product_count = db.scalar(
        select(func.count(Product.id)).where(Product.competitor_id == c.id, Product.is_active.is_(True))
    ) or 0
    blog_count = db.scalar(select(func.count(BlogPost.id)).where(BlogPost.competitor_id == c.id)) or 0
    signal_count = db.scalar(select(func.count(Signal.id)).where(Signal.competitor_id == c.id)) or 0
    last_ingested: Optional[datetime] = db.scalar(
        select(func.max(IngestionRun.finished_at))
        .join(Source, Source.id == IngestionRun.source_id)
        .where(Source.competitor_id == c.id)
    )
    return CompetitorDetail(
        id=c.id,
        slug=c.slug,
        name=c.name,
        website=c.website,
        description=c.description,
        logo_url=c.logo_url,
        brand_weight=c.brand_weight,
        is_anchor=bool(getattr(c, "is_anchor", False)),
        product_count=product_count,
        blog_count=blog_count,
        signal_count=signal_count,
        last_ingested_at=last_ingested,
    )


@router.get("/anchor", response_model=CompetitorDetail)
def get_anchor_brand(db: Session = Depends(get_db)):
    """The single `is_anchor` row (Minimalist) — not part of the peer list."""
    c = db.scalar(select(Competitor).where(Competitor.is_anchor.is_(True)))
    if not c:
        raise HTTPException(404, "no anchor brand configured")
    return _competitor_detail(db, c)


@router.get("", response_model=list[CompetitorDetail])
def list_competitors(
    include_anchor: bool = Query(
        False,
        description="If true, return every tracked brand. Default false: peers only (excludes Minimalist).",
    ),
    db: Session = Depends(get_db),
):
    stmt = select(Competitor)
    if not include_anchor:
        stmt = stmt.where(Competitor.is_anchor.is_(False))
    stmt = stmt.order_by(Competitor.brand_weight.desc())
    comps = list(db.scalars(stmt))
    return [_competitor_detail(db, c) for c in comps]


@router.get("/{slug}", response_model=CompetitorDetail)
def get_competitor(slug: str, db: Session = Depends(get_db)):
    c = db.scalar(select(Competitor).where(Competitor.slug == slug))
    if not c:
        raise HTTPException(404, "competitor not found")
    return _competitor_detail(db, c)
