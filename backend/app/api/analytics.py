"""Analytics over scraped catalog + signals — anchor brand (Minimalist) vs peers."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..intelligence.skincare_actives import extract_from_product
from ..models import Competitor, Product, ProductSnapshot, Signal
from ..schemas import AnalyticsOverview, InsightCard, InsightsResponse
from ..time_utils import utc_now

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _median(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    m = len(s) // 2
    if len(s) % 2:
        return round(s[m], 2)
    return round((s[m - 1] + s[m]) / 2.0, 2)


def _mean(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _percentile(vals: list[float], q: float) -> Optional[float]:
    """Linear interpolation percentile, ``q`` in ``[0, 1]``."""
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return round(s[0], 2)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return round(s[lo], 2)
    return round(s[lo] + (s[hi] - s[lo]) * (pos - lo), 2)


def _latest_snapshot(db: Session, product_id: int) -> Optional[ProductSnapshot]:
    return db.scalar(
        select(ProductSnapshot)
        .where(ProductSnapshot.product_id == product_id)
        .order_by(ProductSnapshot.captured_at.desc())
        .limit(1)
    )


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(
    window_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Aggregate price landscape, active-ingredient mix, and signal velocity vs anchor."""
    since = utc_now() - timedelta(days=window_days)
    since_30 = utc_now() - timedelta(days=30)

    comps = list(db.scalars(select(Competitor).order_by(Competitor.is_anchor.desc(), Competitor.brand_weight.desc())))
    anchor = next((c for c in comps if c.is_anchor), None)
    peers = [c for c in comps if not c.is_anchor]

    price_rows: list[dict[str, Any]] = []
    discount_rows: list[dict[str, Any]] = []
    stock_rows: list[dict[str, Any]] = []
    active_totals: dict[str, int] = {}
    active_by_brand: dict[str, dict[str, int]] = {}
    active_brand_presence: dict[str, set[str]] = defaultdict(set)
    launches_30d: list[dict[str, Any]] = []
    signals_by_brand: list[dict[str, Any]] = []

    for c in comps:
        products = list(
            db.scalars(select(Product).where(Product.competitor_id == c.id, Product.is_active.is_(True)))
        )
        prices: list[float] = []
        currencies: set[str] = set()
        ab: dict[str, int] = {}
        discounted = 0
        priceable = 0
        discount_pcts: list[float] = []

        for p in products:
            snap = _latest_snapshot(db, p.id)
            if snap and snap.price_min is not None:
                px = float(snap.price_min)
                if px > 0:
                    prices.append(px)
                    if snap.currency:
                        currencies.add(snap.currency)
                    priceable += 1
                    cap = snap.compare_at_min
                    if cap is not None and float(cap) > px:
                        discounted += 1
                        discount_pcts.append(round((float(cap) - px) / float(cap) * 100.0, 2))
            for act in extract_from_product(p.title, p.tags or [], p.product_type):
                active_totals[act] = active_totals.get(act, 0) + 1
                ab[act] = ab.get(act, 0) + 1
                active_brand_presence[act].add(c.slug)
            if p.first_seen_at >= since_30:
                launches_30d.append(
                    {"brand_slug": c.slug, "brand_name": c.name, "title": p.title, "first_seen_at": p.first_seen_at.isoformat()}
                )

        if ab:
            active_by_brand[c.slug] = ab

        curr = "mixed" if len(currencies) > 1 else (next(iter(currencies)) if currencies else None)
        price_rows.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "product_count": len(products),
                "median_listed_price": _median(prices),
                "mean_listed_price": _mean(prices),
                "p25_listed_price": _percentile(prices, 0.25),
                "p75_listed_price": _percentile(prices, 0.75),
                "currency": curr,
            }
        )
        discount_rows.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "priceable_skus": priceable,
                "discounted_skus": discounted,
                "discount_share_pct": round((discounted / priceable * 100.0), 1) if priceable else 0.0,
                "median_discount_pct": _median(discount_pcts) or 0.0,
                "max_discount_pct": round(max(discount_pcts), 1) if discount_pcts else 0.0,
            }
        )

        oos_n = db.scalar(
            select(func.count(Signal.id)).where(
                Signal.competitor_id == c.id,
                Signal.created_at >= since,
                Signal.kind == "OUT_OF_STOCK",
            )
        ) or 0
        bis_n = db.scalar(
            select(func.count(Signal.id)).where(
                Signal.competitor_id == c.id,
                Signal.created_at >= since,
                Signal.kind == "BACK_IN_STOCK",
            )
        ) or 0
        stock_rows.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "out_of_stock": oos_n,
                "back_in_stock": bis_n,
                "net_pressure": oos_n - bis_n,
            }
        )

        sig_n = db.scalar(select(func.count(Signal.id)).where(Signal.competitor_id == c.id, Signal.created_at >= since)) or 0
        signals_by_brand.append({"slug": c.slug, "name": c.name, "is_anchor": c.is_anchor, "signals": sig_n})

    top_actives = sorted(
        [{"active": k, "product_hits": v} for k, v in active_totals.items()],
        key=lambda x: x["product_hits"],
        reverse=True,
    )[:15]

    active_cross_brand = sorted(
        (
            {
                "active": k,
                "brands_with_hits": len(v),
                "brand_slugs": sorted(v),
                "product_hits": active_totals.get(k, 0),
            }
            for k, v in active_brand_presence.items()
        ),
        key=lambda x: (x["brands_with_hits"], x["product_hits"]),
        reverse=True,
    )[:30]

    data_quality_notes = [
        "Listed prices use each product's latest snapshot; SKUs with price 0 (samples/gifts) are excluded from price percentiles.",
        "MyGlamm (www.myglamm.com) does not expose public Shopify `products.json`; this repo ships a Shopify-shaped JSON snapshot for apples-to-apples parsing.",
        "Foxtale and Deconstruct are ingested via their Shopify backend URLs (`*.myshopify.com`); shopper domains differ.",
    ]
    if any(r.get("currency") == "mixed" for r in price_rows):
        data_quality_notes.append(
            "Mixed currencies across brands: compare medians within the same currency only, or normalize offline."
        )

    anchor_signals = next((x["signals"] for x in signals_by_brand if x["is_anchor"]), 0)
    peer_signal_sum = sum(x["signals"] for x in signals_by_brand if not x["is_anchor"])
    total_peer_brands = max(1, len(peers))

    if anchor:
        narrative = (
            f"In the last {window_days}d, the anchor brand logged {anchor_signals} signals vs "
            f"{peer_signal_sum} total across {total_peer_brands} peer brands "
            f"({peer_signal_sum / total_peer_brands:.1f} avg per peer)."
        )
    else:
        narrative = "No anchor brand is flagged (is_anchor). Run `python -m app.seed` after upgrading."

    # ---- Launches per ISO week, last 12 weeks (sparkline-friendly).
    weeks_back = 12
    week_cutoff = utc_now() - timedelta(weeks=weeks_back)
    launch_signals = list(
        db.scalars(
            select(Signal)
            .options(selectinload(Signal.competitor))
            .where(Signal.kind == "PRODUCT_LAUNCH", Signal.created_at >= week_cutoff)
        )
    )
    per_brand_week: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in launch_signals:
        if not s.competitor:
            continue
        iso_year, iso_week, _ = s.created_at.isocalendar()
        bucket = f"{iso_year}-W{iso_week:02d}"
        per_brand_week[s.competitor.slug][bucket] += 1
    # Build a stable list of week buckets covering the window (oldest -> newest).
    week_buckets: list[str] = []
    cursor = utc_now() - timedelta(weeks=weeks_back - 1)
    for _ in range(weeks_back):
        iy, iw, _ = cursor.isocalendar()
        week_buckets.append(f"{iy}-W{iw:02d}")
        cursor += timedelta(weeks=1)
    launches_per_week = []
    for c in comps:
        series = [per_brand_week[c.slug].get(wb, 0) for wb in week_buckets]
        launches_per_week.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "weeks": week_buckets,
                "counts": series,
                "total": sum(series),
            }
        )

    # ---- Anchor white-space: actives that 3+ peers have but the anchor doesn't.
    anchor_actives: set[str] = set(active_by_brand.get(anchor.slug, {}).keys()) if anchor else set()
    anchor_whitespace: list[dict[str, Any]] = []
    if anchor:
        for active, brands in active_brand_presence.items():
            peer_brands = brands - {anchor.slug}
            if len(peer_brands) >= 3 and active not in anchor_actives:
                anchor_whitespace.append(
                    {
                        "active": active,
                        "peer_count": len(peer_brands),
                        "peer_slugs": sorted(peer_brands),
                        "peer_sku_hits": active_totals.get(active, 0),
                    }
                )
        anchor_whitespace.sort(key=lambda r: (r["peer_count"], r["peer_sku_hits"]), reverse=True)
        anchor_whitespace = anchor_whitespace[:15]

    # ---- Top price moves in the analytics window (biggest absolute % swings).
    move_signals = list(
        db.scalars(
            select(Signal)
            .options(selectinload(Signal.competitor))
            .where(
                Signal.kind.in_(("PRICE_DROP", "PRICE_INCREASE")),
                Signal.created_at >= since,
            )
        )
    )
    move_records: list[dict[str, Any]] = []
    for s in move_signals:
        delta = s.delta or {}
        pct = delta.get("pct_change")
        old_p = delta.get("old_price")
        new_p = delta.get("new_price")
        if pct is None or old_p is None or new_p is None:
            continue
        try:
            pct_f = float(pct)
        except (TypeError, ValueError):
            continue
        move_records.append(
            {
                "signal_id": s.id,
                "kind": s.kind,
                "brand_slug": s.competitor.slug if s.competitor else None,
                "brand_name": s.competitor.name if s.competitor else None,
                "title": s.title,
                "product_id": s.entity_id,
                "old_price": float(old_p),
                "new_price": float(new_p),
                "pct_change": round(pct_f * 100.0, 1),
                "currency": delta.get("currency"),
                "created_at": s.created_at.isoformat(),
            }
        )
    move_records.sort(key=lambda r: abs(r["pct_change"]), reverse=True)
    top_price_moves = move_records[:20]

    # ---- Cumulative catalog size by ISO week (per brand, last 12 weeks).
    # Uses Product.first_seen_at as a proxy for "in catalog at end of week N".
    week_end_dates: list[Any] = []
    cur_w = utc_now() - timedelta(weeks=weeks_back - 1)
    for _ in range(weeks_back):
        # snap to end of that ISO week (Sunday 23:59) — close-enough for trending.
        iy, iw, _ = cur_w.isocalendar()
        week_end_dates.append((f"{iy}-W{iw:02d}", cur_w))
        cur_w += timedelta(weeks=1)
    catalog_size_weekly: list[dict[str, Any]] = []
    for c in comps:
        # Pull all products' first_seen_at ascending, then count <= each cutoff.
        first_seens = sorted(
            float(t.timestamp())
            for t in db.scalars(
                select(Product.first_seen_at).where(Product.competitor_id == c.id)
            )
            if t is not None
        )
        counts: list[int] = []
        for _label, end in week_end_dates:
            cutoff = end.timestamp()
            # binary search would be neater, but linear is fine for ~hundreds of SKUs.
            counts.append(sum(1 for ts in first_seens if ts <= cutoff))
        catalog_size_weekly.append(
            {
                "slug": c.slug,
                "name": c.name,
                "is_anchor": c.is_anchor,
                "weeks": [w for w, _ in week_end_dates],
                "counts": counts,
                "current": counts[-1] if counts else 0,
            }
        )

    return AnalyticsOverview(
        window_days=window_days,
        anchor_slug=anchor.slug if anchor else None,
        anchor_name=anchor.name if anchor else None,
        narrative=narrative,
        price_landscape=price_rows,
        top_actives_in_catalog=top_actives,
        actives_by_brand=active_by_brand,
        signals_by_brand=signals_by_brand,
        recent_launches_30d=sorted(launches_30d, key=lambda x: x["first_seen_at"], reverse=True)[:200],
        active_cross_brand=active_cross_brand,
        data_quality_notes=data_quality_notes,
        discount_landscape=discount_rows,
        stock_pressure=stock_rows,
        launches_per_week=launches_per_week,
        anchor_whitespace=anchor_whitespace,
        top_price_moves=top_price_moves,
        catalog_size_weekly=catalog_size_weekly,
    )


# --- Auto-generated insights -------------------------------------------------

@router.get("/insights", response_model=InsightsResponse)
def analytics_insights(
    window_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Return 6–10 plain-English findings derived from the analytics overview.

    Designed to be rendered as a strip of cards on the dashboard / analytics top
    so the user sees *interpretation* on landing, not raw rows.
    """
    overview = analytics_overview(window_days=window_days, db=db)  # reuse computation
    cards: list[InsightCard] = []

    anchor_slug = overview.anchor_slug
    anchor_name = overview.anchor_name

    # 1) Launch surge — biggest weekly launch count vs peer median.
    lpw = overview.launches_per_week
    if lpw:
        per_brand_total = [(r, sum(r.get("counts") or [])) for r in lpw]
        per_brand_total.sort(key=lambda x: x[1], reverse=True)
        peer_totals = [t for r, t in per_brand_total if not r.get("is_anchor")]
        peer_median = _median([float(t) for t in peer_totals]) if peer_totals else None
        top = per_brand_total[0] if per_brand_total else None
        if top and top[1] >= 5 and peer_median is not None and top[1] >= peer_median * 1.5:
            r, n = top
            mult = round(n / max(peer_median, 0.5), 1)
            cards.append(
                InsightCard(
                    id=f"launch-surge-{r['slug']}",
                    severity="warning" if not r.get("is_anchor") else "success",
                    headline=f"{r['name']} is launching {mult}× the peer median",
                    detail=(
                        f"{n} new SKUs over the last 12 weeks vs a peer median of "
                        f"{peer_median:.0f}. Watch the catalog for category overlap with anchor."
                    ),
                    metric=f"{n} launches / 12w",
                    brand_slug=r["slug"],
                    brand_name=r["name"],
                    href=f"/competitors/{r['slug']}",
                )
            )

    # 2) Discount aggressor — peer with highest discount share AND >= 10% on sale.
    disc = overview.discount_landscape
    peers_disc = [r for r in disc if not r.get("is_anchor")]
    if peers_disc:
        top_d = max(peers_disc, key=lambda r: r.get("discount_share_pct") or 0)
        if (top_d.get("discount_share_pct") or 0) >= 10:
            cards.append(
                InsightCard(
                    id=f"discount-aggressor-{top_d['slug']}",
                    severity="warning",
                    headline=f"{top_d['name']} is discounting {top_d['discount_share_pct']}% of catalog",
                    detail=(
                        f"{top_d.get('discounted_skus', 0)} of {top_d.get('priceable_skus', 0)} priced SKUs "
                        f"are visibly on sale (median {top_d.get('median_discount_pct', 0)}% off). "
                        "Pricing pressure on overlapping shelves."
                    ),
                    metric=f"{top_d['discount_share_pct']}% on sale",
                    brand_slug=top_d["slug"],
                    brand_name=top_d["name"],
                    href=f"/competitors/{top_d['slug']}",
                )
            )

    # 3) Anchor pricing position — vs peer median (cheapest / priciest).
    pl = overview.price_landscape
    anchor_row = next((r for r in pl if r.get("is_anchor")), None)
    peer_rows_priced = [r for r in pl if not r.get("is_anchor") and r.get("median_listed_price")]
    if anchor_row and anchor_row.get("median_listed_price") and peer_rows_priced:
        a_med = float(anchor_row["median_listed_price"])
        peer_meds = [float(r["median_listed_price"]) for r in peer_rows_priced]
        peer_med = _median(peer_meds) or 0.0
        if peer_med > 0:
            delta_pct = round((a_med - peer_med) / peer_med * 100.0, 1)
            if delta_pct <= -10:
                cards.append(
                    InsightCard(
                        id="anchor-cheapest",
                        severity="success",
                        headline=f"{anchor_name} is {abs(delta_pct)}% cheaper than peer median",
                        detail=(
                            f"Anchor median {a_med:.0f} vs peer median {peer_med:.0f}. "
                            "Strong value position — promote pricing in marketing copy."
                        ),
                        metric=f"{delta_pct}% vs peers",
                        brand_slug=anchor_slug,
                        brand_name=anchor_name,
                        href="/compare",
                    )
                )
            elif delta_pct >= 15:
                cards.append(
                    InsightCard(
                        id="anchor-priciest",
                        severity="danger",
                        headline=f"{anchor_name} is {delta_pct}% pricier than peer median",
                        detail=(
                            f"Anchor median {a_med:.0f} vs peer median {peer_med:.0f}. "
                            "Either justify with claims/ingredients or risk losing on price-led queries."
                        ),
                        metric=f"+{delta_pct}% vs peers",
                        brand_slug=anchor_slug,
                        brand_name=anchor_name,
                        href="/compare",
                    )
                )

    # 4) Anchor white-space — biggest portfolio gap.
    ws = overview.anchor_whitespace
    if ws:
        top_gap = ws[0]
        cards.append(
            InsightCard(
                id=f"whitespace-{top_gap['active']}",
                severity="warning",
                headline=f"White-space: no {top_gap['active'].replace('_', ' ')} in anchor catalog",
                detail=(
                    f"{top_gap['peer_count']} peers ship it ({top_gap['peer_sku_hits']} SKUs total) — "
                    f"peers: {', '.join(top_gap['peer_slugs'])}."
                ),
                metric=f"{top_gap['peer_count']} peers in",
                href="/analytics",
            )
        )

    # 5) Stock pressure — net OOS - BIS for any peer in window.
    sp = overview.stock_pressure or []
    peers_sp = [r for r in sp if not r.get("is_anchor") and (r.get("out_of_stock") or 0) >= 3]
    if peers_sp:
        top_oos = max(peers_sp, key=lambda r: r.get("net_pressure", 0))
        if top_oos.get("net_pressure", 0) >= 3:
            cards.append(
                InsightCard(
                    id=f"stock-pressure-{top_oos['slug']}",
                    severity="info",
                    headline=f"{top_oos['name']} is selling through faster than restocking",
                    detail=(
                        f"{top_oos['out_of_stock']} sold out vs {top_oos['back_in_stock']} back in "
                        f"stock in the last {window_days} days — net +{top_oos['net_pressure']}. "
                        "Possible supply gap to capture."
                    ),
                    metric=f"net +{top_oos['net_pressure']} OOS",
                    brand_slug=top_oos["slug"],
                    brand_name=top_oos["name"],
                    href=f"/competitors/{top_oos['slug']}",
                )
            )

    # 6) Top single price move.
    moves = overview.top_price_moves or []
    if moves:
        m = moves[0]
        kind_text = "dropped" if m["kind"] == "PRICE_DROP" else "raised"
        sev = "success" if m["kind"] == "PRICE_DROP" else "danger"
        cards.append(
            InsightCard(
                id=f"top-move-{m['signal_id']}",
                severity=sev,
                headline=f"{m['brand_name']} {kind_text} '{m['title'][:60]}' by {abs(m['pct_change'])}%",
                detail=(
                    f"{m['old_price']:.0f} → {m['new_price']:.0f} {m.get('currency') or ''}. "
                    "Biggest single-SKU move in the window."
                ),
                metric=f"{m['pct_change']}%",
                brand_slug=m.get("brand_slug"),
                brand_name=m.get("brand_name"),
                href=f"/products/{m['product_id']}" if m.get("product_id") else "/feed",
            )
        )

    # 7) Crowded category warning (most-shared active across brands).
    xb = overview.active_cross_brand
    if xb:
        most_crowded = max(xb, key=lambda r: r.get("brands_with_hits", 0))
        if most_crowded.get("brands_with_hits", 0) >= 4:
            cards.append(
                InsightCard(
                    id=f"crowded-{most_crowded['active']}",
                    severity="info",
                    headline=(
                        f"{most_crowded['active'].replace('_', ' ').title()} is the most "
                        f"crowded shelf ({most_crowded['brands_with_hits']} brands)"
                    ),
                    detail=(
                        f"{most_crowded['product_hits']} SKUs total across "
                        f"{most_crowded['brands_with_hits']} brands. Lean into clear differentiation "
                        "or consider deprioritising new launches here."
                    ),
                    metric=f"{most_crowded['brands_with_hits']} brands",
                    href="/analytics",
                )
            )

    # 8) Catalog growth leader (last 12 weeks delta).
    csw = overview.catalog_size_weekly or []
    if csw:
        growth = []
        for r in csw:
            counts = r.get("counts") or []
            if len(counts) >= 2 and counts[0] > 0:
                delta = counts[-1] - counts[0]
                growth.append((r, delta, round(delta / counts[0] * 100.0, 1)))
        growth.sort(key=lambda x: x[2], reverse=True)
        if growth and growth[0][2] >= 5:
            r, delta, pct = growth[0]
            cards.append(
                InsightCard(
                    id=f"catalog-growth-{r['slug']}",
                    severity="warning" if not r.get("is_anchor") else "success",
                    headline=f"{r['name']} catalog grew {pct}% in 12 weeks",
                    detail=(
                        f"+{delta} SKUs (now {r['counts'][-1]}). Fastest portfolio expansion "
                        "in the peer set."
                    ),
                    metric=f"+{pct}%",
                    brand_slug=r["slug"],
                    brand_name=r["name"],
                    href=f"/competitors/{r['slug']}",
                )
            )

    # Always include at least one finding so the strip is never empty.
    if not cards:
        cards.append(
            InsightCard(
                id="ok-quiet",
                severity="info",
                headline="It's quiet on the shelf",
                detail=(
                    "No major launch surges, price moves, or stock pressure events in this window. "
                    "Try a longer window or wait for the next ingestion."
                ),
                href="/feed",
            )
        )

    return InsightsResponse(
        window_days=window_days,
        anchor_slug=anchor_slug,
        anchor_name=anchor_name,
        insights=cards,
    )
