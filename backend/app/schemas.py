from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompetitorOut(ORMModel):
    id: int
    slug: str
    name: str
    website: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    brand_weight: float
    is_anchor: bool = False


class CompetitorDetail(CompetitorOut):
    product_count: int
    blog_count: int
    signal_count: int
    last_ingested_at: Optional[datetime] = None


class ProductSnapshotOut(ORMModel):
    captured_at: datetime
    price_min: Optional[float]
    price_max: Optional[float]
    compare_at_min: Optional[float] = None
    compare_at_max: Optional[float] = None
    currency: Optional[str]
    available: bool
    variants_count: int


class ProductOut(ORMModel):
    id: int
    competitor_id: int
    competitor_name: Optional[str] = None
    competitor_slug: Optional[str] = None
    external_id: str
    handle: Optional[str]
    title: str
    product_type: Optional[str]
    url: Optional[str]
    image_url: Optional[str]
    tags: list[str]
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    latest_price_min: Optional[float] = None
    latest_price_max: Optional[float] = None
    currency: Optional[str] = None


class ProductDetail(ProductOut):
    snapshots: list[ProductSnapshotOut] = []


class BlogPostOut(ORMModel):
    id: int
    competitor_id: int
    competitor_name: Optional[str] = None
    title: str
    url: str
    summary: Optional[str]
    published_at: Optional[datetime]
    first_seen_at: datetime


class SignalOut(ORMModel):
    id: int
    competitor_id: int
    competitor_name: Optional[str] = None
    competitor_slug: Optional[str] = None
    kind: str
    entity_type: str
    entity_id: Optional[int]
    title: str
    description: Optional[str]
    delta: dict[str, Any]
    themes: list[str]
    importance: float
    created_at: datetime


class SocialMentionOut(ORMModel):
    id: int
    competitor_id: int
    competitor_name: Optional[str] = None
    competitor_slug: Optional[str] = None
    platform: str
    external_id: str
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
    first_seen_at: datetime


class TopCreatorOut(BaseModel):
    competitor_slug: str
    competitor_name: str
    platform: str
    author: str
    author_handle: Optional[str] = None
    author_url: Optional[str] = None
    mention_count: int
    total_views: Optional[int] = None
    total_score: Optional[int] = None
    sample_url: Optional[str] = None


class IngestionRunOut(ORMModel):
    id: int
    source_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    items_seen: int
    items_new: int
    items_changed: int
    signals_created: int
    error: Optional[str]


class DashboardSummary(BaseModel):
    window_days: int
    total_signals: int
    new_products: int
    price_drops: int
    price_increases: int
    blog_posts: int
    top_themes: list[dict[str, Any]]
    by_competitor: list[dict[str, Any]]


class IngestResult(BaseModel):
    runs: list[IngestionRunOut]
    total_signals: int


class AnalyticsOverview(BaseModel):
    """Cross-brand analytics: price landscape, actives mix, signal share vs anchor."""

    window_days: int
    anchor_slug: Optional[str] = None
    anchor_name: Optional[str] = None
    narrative: str = ""
    price_landscape: list[dict[str, Any]]
    top_actives_in_catalog: list[dict[str, Any]]
    actives_by_brand: dict[str, dict[str, int]]
    signals_by_brand: list[dict[str, Any]]
    recent_launches_30d: list[dict[str, Any]]
    # Drill-down: cross-brand ingredient overlap; notes for interviewer-facing caveats.
    active_cross_brand: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)

    # Sales / commercial insights (added in v0.2)
    discount_landscape: list[dict[str, Any]] = Field(default_factory=list)
    stock_pressure: list[dict[str, Any]] = Field(default_factory=list)
    launches_per_week: list[dict[str, Any]] = Field(default_factory=list)
    anchor_whitespace: list[dict[str, Any]] = Field(default_factory=list)
    top_price_moves: list[dict[str, Any]] = Field(default_factory=list)
    catalog_size_weekly: list[dict[str, Any]] = Field(default_factory=list)


class InsightCard(BaseModel):
    """One auto-generated finding for the dashboard / analytics narrative strip."""

    id: str
    severity: str = "info"  # one of: info, success, warning, danger
    headline: str
    detail: str
    metric: Optional[str] = None
    brand_slug: Optional[str] = None
    brand_name: Optional[str] = None
    href: Optional[str] = None


class InsightsResponse(BaseModel):
    window_days: int
    anchor_slug: Optional[str] = None
    anchor_name: Optional[str] = None
    insights: list[InsightCard]
