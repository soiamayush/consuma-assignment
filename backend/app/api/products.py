from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Competitor, Product, ProductSnapshot
from ..schemas import ProductDetail, ProductOut, ProductSnapshotOut

router = APIRouter(prefix="/api/products", tags=["products"])

# India peer set + anchor: Shopify JSON uses INR amounts; older rows may have ``currency=NULL``.
_INR_BRAND_SLUGS = frozenset(
    {"minimalist", "pilgrim", "mamaearth", "myglamm", "bellavita", "foxtale", "deconstruct"}
)


def _display_currency(competitor: Competitor, snapshot_currency: str | None) -> str | None:
    if snapshot_currency:
        return snapshot_currency
    if competitor.slug in _INR_BRAND_SLUGS:
        return "INR"
    return None


def _snapshot_out(s: ProductSnapshot, competitor: Competitor) -> ProductSnapshotOut:
    return ProductSnapshotOut(
        captured_at=s.captured_at,
        price_min=s.price_min,
        price_max=s.price_max,
        compare_at_min=getattr(s, "compare_at_min", None),
        compare_at_max=getattr(s, "compare_at_max", None),
        currency=_display_currency(competitor, s.currency),
        available=s.available,
        variants_count=s.variants_count,
    )


def _latest_snapshot(db: Session, product_id: int) -> Optional[ProductSnapshot]:
    return db.scalar(
        select(ProductSnapshot)
        .where(ProductSnapshot.product_id == product_id)
        .order_by(ProductSnapshot.captured_at.desc())
        .limit(1)
    )


@router.get("", response_model=list[ProductOut])
def list_products(
    response: Response,
    competitor: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    base = select(Product).where(Product.is_active.is_(True))
    if competitor:
        base = base.join(Competitor).where(Competitor.slug == competitor)
    if q:
        base = base.where(Product.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    stmt = (
        base.options(selectinload(Product.competitor))
        .order_by(Product.last_seen_at.desc())
        .offset(offset)
        .limit(limit)
    )
    products = list(db.scalars(stmt))

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    out: list[ProductOut] = []
    for p in products:
        snap = _latest_snapshot(db, p.id)
        out.append(
            ProductOut(
                id=p.id,
                competitor_id=p.competitor_id,
                competitor_name=p.competitor.name,
                competitor_slug=p.competitor.slug,
                external_id=p.external_id,
                handle=p.handle,
                title=p.title,
                product_type=p.product_type,
                url=p.url,
                image_url=p.image_url,
                tags=p.tags or [],
                first_seen_at=p.first_seen_at,
                last_seen_at=p.last_seen_at,
                is_active=p.is_active,
                latest_price_min=snap.price_min if snap else None,
                latest_price_max=snap.price_max if snap else None,
                currency=_display_currency(p.competitor, snap.currency if snap else None),
            )
        )
    return out


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.scalar(
        select(Product)
        .options(selectinload(Product.competitor), selectinload(Product.snapshots))
        .where(Product.id == product_id)
    )
    if not p:
        raise HTTPException(404, "product not found")
    latest = p.snapshots[0] if p.snapshots else None
    return ProductDetail(
        id=p.id,
        competitor_id=p.competitor_id,
        competitor_name=p.competitor.name,
        competitor_slug=p.competitor.slug,
        external_id=p.external_id,
        handle=p.handle,
        title=p.title,
        product_type=p.product_type,
        url=p.url,
        image_url=p.image_url,
        tags=p.tags or [],
        first_seen_at=p.first_seen_at,
        last_seen_at=p.last_seen_at,
        is_active=p.is_active,
        latest_price_min=latest.price_min if latest else None,
        latest_price_max=latest.price_max if latest else None,
        currency=_display_currency(p.competitor, latest.currency if latest else None),
        snapshots=[_snapshot_out(s, p.competitor) for s in p.snapshots],
    )


@router.get("/{product_id}/peers")
def get_product_peers(product_id: int, db: Session = Depends(get_db)):
    """Cross-brand peer comparison for a single SKU.

    Returns the cheapest, closest-priced, and most-expensive peer SKU in the
    same ``product_type`` category, plus a few alternatives. The ``self`` block
    echoes the focal SKU so the UI can render a single shared layout.
    """
    p = db.scalar(
        select(Product).options(selectinload(Product.competitor)).where(Product.id == product_id)
    )
    if not p:
        raise HTTPException(404, "product not found")
    self_snap = _latest_snapshot(db, p.id)
    self_price = float(self_snap.price_min) if self_snap and self_snap.price_min else None

    def _to_card(prod: Product, snap: ProductSnapshot | None) -> dict[str, object | None]:
        cur = _display_currency(prod.competitor, snap.currency if snap else None)
        return {
            "id": prod.id,
            "title": prod.title,
            "url": prod.url,
            "image_url": prod.image_url,
            "product_type": prod.product_type,
            "brand_slug": prod.competitor.slug,
            "brand_name": prod.competitor.name,
            "is_anchor": prod.competitor.is_anchor,
            "price_min": float(snap.price_min) if snap and snap.price_min is not None else None,
            "price_max": float(snap.price_max) if snap and snap.price_max is not None else None,
            "compare_at_min": float(snap.compare_at_min)
            if snap and snap.compare_at_min is not None
            else None,
            "currency": cur,
        }

    self_payload = _to_card(p, self_snap)

    # Pull peer SKUs in the same product_type from OTHER brands.
    if not p.product_type:
        return {
            "self": self_payload,
            "category": None,
            "cheapest": None,
            "closest": None,
            "most_expensive": None,
            "alternatives": [],
            "note": "This SKU has no product_type tag, so peer matching by category isn't possible.",
        }

    peer_products = list(
        db.scalars(
            select(Product)
            .options(selectinload(Product.competitor))
            .where(
                Product.is_active.is_(True),
                Product.competitor_id != p.competitor_id,
                Product.product_type.isnot(None),
                func.lower(Product.product_type) == p.product_type.lower(),
            )
        )
    )

    peers: list[tuple[Product, ProductSnapshot | None, float | None]] = []
    for pp in peer_products:
        snap = _latest_snapshot(db, pp.id)
        px = float(snap.price_min) if snap and snap.price_min and float(snap.price_min) > 0 else None
        peers.append((pp, snap, px))

    priced = [t for t in peers if t[2] is not None]

    cheapest_t = min(priced, key=lambda t: t[2]) if priced else None
    most_expensive_t = max(priced, key=lambda t: t[2]) if priced else None
    closest_t = (
        min(priced, key=lambda t: abs(t[2] - self_price))
        if (priced and self_price is not None)
        else None
    )

    used_ids = {t[0].id for t in (cheapest_t, closest_t, most_expensive_t) if t}
    alternatives = sorted(
        (t for t in priced if t[0].id not in used_ids),
        key=lambda t: abs(t[2] - (self_price or t[2])),
    )[:6]

    return {
        "self": self_payload,
        "category": p.product_type,
        "peer_count": len(priced),
        "cheapest": _to_card(*cheapest_t[:2]) if cheapest_t else None,
        "closest": _to_card(*closest_t[:2]) if closest_t else None,
        "most_expensive": _to_card(*most_expensive_t[:2]) if most_expensive_t else None,
        "alternatives": [_to_card(prod, snap) for prod, snap, _ in alternatives],
    }
