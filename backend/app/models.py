"""SQLAlchemy ORM models.

Schema overview:

- Competitor: a brand we track.
- Source: an ingestion endpoint tied to a competitor (e.g. Shopify products JSON, blog Atom).
- IngestionRun: one execution of a source; used for observability + incremental runs.
- Product: a canonical product for a competitor (by stable external id).
- ProductSnapshot: immutable captures over time used for change detection.
- BlogPost: press / changelog / blog item.
- Signal: derived event surfaced in the UI (price drop, launch, etc.), with an importance score.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Manual weight 0..1 for importance scoring (e.g. a more-watched competitor ranks higher).
    brand_weight: Mapped[float] = mapped_column(Float, default=0.5)
    # True for the single "your brand" we benchmark peers against (Minimalist in this product).
    is_anchor: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sources: Mapped[list["Source"]] = relationship(back_populates="competitor", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship(back_populates="competitor", cascade="all, delete-orphan")
    blog_posts: Mapped[list["BlogPost"]] = relationship(back_populates="competitor", cascade="all, delete-orphan")
    signals: Mapped[list["Signal"]] = relationship(back_populates="competitor", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    # e.g. "shopify_products", "shopify_blog_atom", "fixture_products", "fixture_blog"
    kind: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(1000))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    competitor: Mapped[Competitor] = relationship(back_populates="sources")
    runs: Mapped[list["IngestionRun"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|ok|error|partial
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_changed: Mapped[int] = mapped_column(Integer, default=0)
    signals_created: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="runs")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("competitor_id", "external_id", name="uq_product_competitor_external"),
        Index("ix_product_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)  # Shopify product id
    handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    product_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    vendor: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    competitor: Mapped[Competitor] = relationship(back_populates="products")
    snapshots: Mapped[list["ProductSnapshot"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductSnapshot.captured_at.desc()",
    )


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (Index("ix_snap_product_time", "product_id", "captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    title: Mapped[str] = mapped_column(String(500))
    price_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Shopify `compare_at_price` (list / MSRP) when on sale — optional for charts.
    compare_at_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    compare_at_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    variants_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    product: Mapped[Product] = relationship(back_populates="snapshots")


class BlogPost(Base):
    __tablename__ = "blog_posts"
    __table_args__ = (
        UniqueConstraint("competitor_id", "external_id", name="uq_blog_competitor_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64))

    competitor: Mapped[Competitor] = relationship(back_populates="blog_posts")


class SocialMention(Base):
    """A buzz/PR data point for a brand (YouTube video, Reddit post, news article, …).

    Stored in a single table keyed by ``(competitor_id, platform, external_id)`` so the same
    upsert flow as products/blogs works.  ``metric_views`` and ``metric_score`` are platform-
    specific (e.g. YouTube view count vs Reddit upvote score) but normalised to ints so we
    can rank cross-platform.
    """

    __tablename__ = "social_mentions"
    __table_args__ = (
        UniqueConstraint(
            "competitor_id", "platform", "external_id", name="uq_social_competitor_platform_external"
        ),
        Index("ix_social_published", "published_at"),
        Index("ix_social_platform", "platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)  # youtube|news|news_bing|podcast|instagram
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # display name
    author_handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # channel id / host / outlet
    author_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    metric_views: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metric_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metric_comments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    competitor: Mapped[Competitor] = relationship()


class Signal(Base):
    """A surfaced event. Importance is computed at write-time but also re-rankable.

    kind values:
        PRODUCT_LAUNCH, PRODUCT_REMOVED, PRICE_DROP, PRICE_INCREASE,
        BACK_IN_STOCK, OUT_OF_STOCK, BLOG_POST, CATALOG_SURGE
    """

    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signal_importance", "importance"),
        Index("ix_signal_created", "created_at"),
        UniqueConstraint("dedupe_key", name="uq_signal_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(16))  # product | blog | competitor
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delta: Mapped[dict] = mapped_column(JSON, default=dict)
    themes: Mapped[list] = mapped_column(JSON, default=list)
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    dedupe_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    competitor: Mapped[Competitor] = relationship(back_populates="signals")
