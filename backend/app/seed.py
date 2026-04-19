"""Seed the database: **Minimalist** (anchor) vs India clean-beauty / ingredient-led peers.

Public Shopify JSON (`/products.json`) and Atom blogs where available. Some peers
use a **custom domain** for shoppers but the same Shopify backend on a
``*.myshopify.com`` host for ingestion. **MyGlamm** has no public catalog JSON on
``myglamm.com``; we ship a **committed JSON snapshot** AND a real
``myglamm_internal_api`` scraper that can hit ``api.myglamm.com`` directly when
``USE_FIXTURES=false``.

Run: `python -m app.seed`

Idempotent: re-running updates competitor metadata and `is_anchor` flags.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from .config import get_settings
from .db import Base, engine, init_db, session_scope
from .models import Competitor, Source

logger = logging.getLogger(__name__)


COMPETITORS = [
    {
        "slug": "minimalist",
        "name": "Minimalist",
        "website": "https://www.beminimalist.co",
        "description": "Anchor: science-led, ingredient-forward skincare (India).",
        "logo_url": "https://www.beminimalist.co/favicon.ico",
        "brand_weight": 1.0,
        "is_anchor": True,
        "sources": [
            {"kind": "shopify_products", "url": "https://www.beminimalist.co/products.json"},
        ],
    },
    {
        "slug": "pilgrim",
        "name": "Pilgrim",
        "website": "https://discoverpilgrim.com",
        "description": "Peer: K-beauty inspired, ingredient storytelling; overlaps serums and SPF shelf.",
        "logo_url": "https://discoverpilgrim.com/favicon.ico",
        "brand_weight": 0.92,
        "is_anchor": False,
        "sources": [
            {"kind": "shopify_products", "url": "https://discoverpilgrim.com/products.json"},
            {"kind": "shopify_blog_atom", "url": "https://discoverpilgrim.com/blogs/news.atom"},
        ],
    },
    {
        "slug": "myglamm",
        "name": "MyGlamm",
        "website": "https://www.myglamm.com",
        "description": "Peer: mass beauty + skincare; not a Shopify storefront. Real scrape via internal API + Playwright fallback.",
        "logo_url": "https://www.myglamm.com/favicon.ico",
        "brand_weight": 0.9,
        "is_anchor": False,
        "sources": [
            # Real scraper hitting the React app's internal product API.
            {
                "kind": "myglamm_internal_api",
                "url": "https://api.myglamm.com/v3/products",
                "config": {"categories": ["face-skincare", "skincare"], "max_pages": 4},
            },
            # Browser-rendered fallback for when the JSON API blocks us.
            {
                "kind": "browser_listing",
                "url": "https://www.myglamm.com/skincare",
                "config": {
                    "store": "myglamm.com",
                    "product_card_selector": "[data-testid='product-card'], .product-card, a[href*='/p/']",
                    "title_selector": ".product-title, h3, h4",
                    "price_selector": "[class*='price'], .product-price",
                    "image_selector": "img",
                    "wait_for_selector": "[data-testid='product-card'], .product-card, a[href*='/p/']",
                    "scroll_steps": 6,
                    "enabled": False,
                },
            },
        ],
    },
    {
        "slug": "mamaearth",
        "name": "Mamaearth",
        "website": "https://mamaearth.in",
        "description": "Peer: large natural-positioned catalog; frequent launches and promos.",
        "logo_url": "https://mamaearth.in/favicon.ico",
        "brand_weight": 0.88,
        "is_anchor": False,
        "sources": [
            # `/products.json` is gated by Mamaearth's CDN (returns a 'fraud' redirect HTML).
            # Real free path: walk sitemap.xml and parse JSON-LD on each PDP.
            {
                "kind": "mamaearth_sitemap",
                "url": "https://mamaearth.in/sitemap.xml",
                "config": {"product_path": "/product/", "max_products": 60, "delay_ms": 250},
            },
            {"kind": "shopify_blog_atom", "url": "https://mamaearth.in/blogs/goodness-blog.atom"},
        ],
    },
    {
        "slug": "bellavita",
        "name": "Bellavita",
        "website": "https://www.bellavitaorganic.com",
        "description": "Peer: fragrance-forward D2C with broad personal care; overlaps body and face.",
        "logo_url": "https://www.bellavitaorganic.com/favicon.ico",
        "brand_weight": 0.82,
        "is_anchor": False,
        "sources": [
            {"kind": "shopify_products", "url": "https://www.bellavitaorganic.com/products.json"},
        ],
    },
    {
        "slug": "foxtale",
        "name": "Foxtale",
        "website": "https://foxtale.in",
        "description": "Peer: performance skincare/body; storefront uses Shopify backend (myshopify host).",
        "logo_url": "https://foxtale.in/favicon.ico",
        "brand_weight": 0.86,
        "is_anchor": False,
        "sources": [
            {
                "kind": "shopify_products",
                "url": "https://foxtale-consumer.myshopify.com/products.json",
            },
            {
                "kind": "shopify_blog_atom",
                "url": "https://foxtale-consumer.myshopify.com/blogs/news.atom",
            },
        ],
    },
    {
        "slug": "deconstruct",
        "name": "Deconstruct",
        "website": "https://thedeconstruct.in",
        "description": "Peer: acid-led, ingredient-clinical positioning; Shopify on myshopify host.",
        "logo_url": "https://thedeconstruct.in/favicon.ico",
        "brand_weight": 0.91,
        "is_anchor": False,
        "sources": [
            {
                "kind": "shopify_products",
                "url": "https://thedeconstruct.myshopify.com/products.json",
            },
        ],
    },
]


# Per-brand search query for buzz scrapers. Tuned to disambiguate brands
# that share a generic noun ("Pilgrim", "Foxtale") from unrelated content.
SOCIAL_QUERIES: dict[str, str] = {
    "minimalist": "Minimalist skincare",
    "pilgrim": "Discover Pilgrim",
    "myglamm": "MyGlamm",
    "mamaearth": "Mamaearth",
    "bellavita": "Bellavita Organic",
    "foxtale": "Foxtale skincare",
    "deconstruct": "Deconstruct skincare",
}

# Hashtags for Instagram Graph API (no spaces; letters / digits / underscore).
INSTAGRAM_HASHTAGS: dict[str, str] = {
    "minimalist": "beminimalist",
    "pilgrim": "discoverpilgrim",
    "myglamm": "myglamm",
    "mamaearth": "mamaearth",
    "bellavita": "bellavita",
    "foxtale": "foxtale",
    "deconstruct": "deconstructskincare",
}


def social_sources_for(slug: str) -> list[dict]:
    """Build buzz sources for a brand.

    Free paths: YouTube (optional key), Google + Bing News RSS, Apple Podcasts.
    **Instagram** uses Meta's official Graph API when ``INSTAGRAM_ACCESS_TOKEN``
    and ``INSTAGRAM_GRAPH_USER_ID`` are set; otherwise that source is a no-op.
    """
    query = SOCIAL_QUERIES.get(slug)
    if not query:
        return []
    ig_tag = INSTAGRAM_HASHTAGS.get(slug)
    out: list[dict] = [
        {
            "kind": "youtube_search",
            "url": f"youtube:{query}",
            "config": {
                "query": query,
                "window_days": 90,
                "max_results": 25,
                "region_code": "IN",
                "relevance_language": "en",
            },
        },
        {
            "kind": "news_rss",
            "url": f"news:{query}",
            "config": {"query": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en", "max_items": 25},
        },
        {
            "kind": "bing_news_rss",
            "url": f"bing_news:{query}",
            "config": {"query": query, "max_items": 25},
        },
        {
            "kind": "itunes_podcast",
            "url": f"podcast:{query}",
            "config": {"query": query, "country": "in", "limit": 25},
        },
    ]
    if ig_tag:
        out.append(
            {
                "kind": "instagram_graph_hashtag",
                "url": f"instagram:{ig_tag}",
                "config": {"hashtag": ig_tag},
            }
        )
    return out


FIXTURE_MAP = {
    "minimalist": [
        {"kind": "fixture_products", "url": "minimalist_products.json", "config": {"store": "beminimalist.co"}},
        {"kind": "fixture_blog", "url": "minimalist_blog.json"},
    ],
    "pilgrim": [
        {"kind": "fixture_products", "url": "pilgrim_products.json", "config": {"store": "discoverpilgrim.com"}},
        {"kind": "fixture_blog", "url": "pilgrim_blog.json"},
    ],
    "myglamm": [
        {"kind": "fixture_products", "url": "myglamm_products.json", "config": {"store": "myglamm.com"}},
    ],
    "mamaearth": [
        {"kind": "fixture_products", "url": "mamaearth_products.json", "config": {"store": "mamaearth.in"}},
        {"kind": "fixture_blog", "url": "mamaearth_blog.json"},
    ],
    "bellavita": [
        {"kind": "fixture_products", "url": "bellavita_products.json", "config": {"store": "bellavitaorganic.com"}},
    ],
    "foxtale": [
        {"kind": "fixture_products", "url": "foxtale_products.json", "config": {"store": "foxtale.in"}},
        {"kind": "fixture_blog", "url": "foxtale_blog.json"},
    ],
    "deconstruct": [
        {"kind": "fixture_products", "url": "deconstruct_products.json", "config": {"store": "thedeconstruct.in"}},
    ],
}


def seed() -> None:
    settings = get_settings()
    init_db()
    with session_scope() as db:
        for spec in COMPETITORS:
            comp = db.scalar(select(Competitor).where(Competitor.slug == spec["slug"]))
            if comp is None:
                comp = Competitor(
                    slug=spec["slug"],
                    name=spec["name"],
                    website=spec["website"],
                    description=spec["description"],
                    logo_url=spec["logo_url"],
                    brand_weight=spec["brand_weight"],
                    is_anchor=bool(spec.get("is_anchor", False)),
                )
                db.add(comp)
                db.flush()
            else:
                comp.name = spec["name"]
                comp.website = spec["website"]
                comp.description = spec["description"]
                comp.logo_url = spec["logo_url"]
                comp.brand_weight = spec["brand_weight"]
                comp.is_anchor = bool(spec.get("is_anchor", False))

            wanted_sources: list[dict] = (
                list(FIXTURE_MAP.get(spec["slug"], [])) if settings.use_fixtures else list(spec["sources"])
            )
            if (
                not settings.use_fixtures
                and settings.hybrid_fixture_fallback
                and spec["slug"] in ("mamaearth", "myglamm")
            ):
                for fb in FIXTURE_MAP.get(spec["slug"], []):
                    ent = dict(fb)
                    ent["config"] = {**(fb.get("config") or {}), "only_if_empty_fallback": True}
                    wanted_sources.append(ent)

            # Social/buzz sources run in both fixture and live modes — they hit
            # third-party public APIs/RSS so they don't depend on the brand's storefront.
            wanted_sources.extend(social_sources_for(spec["slug"]))

            existing = {(s.kind, s.url): s for s in comp.sources}
            wanted_keys: set[tuple[str, str]] = set()
            for src_spec in wanted_sources:
                key = (src_spec["kind"], src_spec["url"])
                wanted_keys.add(key)
                cfg = src_spec.get("config", {}) or {}
                # `enabled` flag inside config is hoisted to the Source row so the seed
                # can disable noisy/expensive scrapers (browser renders) by default.
                row_enabled = bool(cfg.pop("enabled", True))
                if key in existing:
                    existing[key].config = cfg
                    existing[key].enabled = row_enabled
                else:
                    db.add(
                        Source(
                            competitor_id=comp.id,
                            kind=src_spec["kind"],
                            url=src_spec["url"],
                            config=cfg,
                            enabled=row_enabled,
                        )
                    )
            for key, src in existing.items():
                if key not in wanted_keys:
                    src.enabled = False

    print("Seeded competitors:", ", ".join(c["slug"] for c in COMPETITORS))
    if settings.use_fixtures:
        print("(USE_FIXTURES=true — using fixture-backed sources)")


EXPECTED_SLUGS = frozenset(c["slug"] for c in COMPETITORS)


def _run_fixture_double_ingest() -> None:
    """Regenerate two rounds of JSON fixtures + two ingestion passes (matches `bootstrap`)."""
    import sys

    from .db import session_scope
    from .ingestion.runner import run_all
    from .scripts.make_fixtures import main as make_fixtures_main

    sys.argv = ["make_fixtures", "--round", "1"]
    make_fixtures_main()
    with session_scope() as db:
        run_all(db)
    sys.argv = ["make_fixtures", "--round", "2"]
    make_fixtures_main()
    with session_scope() as db:
        run_all(db)


def reconcile_database_with_current_seed() -> None:
    """Align SQLite with this repo's seed after a code change.

    - Stale slug set       → drop schema + reseed + (fixtures mode) double-ingest.
    - Empty DB             → seed + (fixtures mode) double-ingest.
    - Matching slugs but ANY peer has 0 products → re-run double-ingest so the
      UI never lands on an empty state right after I rotate the peer list.
    """
    from .models import Product

    settings = get_settings()
    if not str(engine.url).startswith("sqlite"):
        return

    init_db()
    with session_scope() as db:
        n = db.scalar(select(func.count()).select_from(Competitor)) or 0
        slugs = set(db.scalars(select(Competitor.slug))) if n else set()
        peer_product_min = 0
        if slugs == EXPECTED_SLUGS:
            counts = db.execute(
                select(Competitor.slug, func.count(Product.id))
                .outerjoin(Product, Product.competitor_id == Competitor.id)
                .where(Competitor.is_anchor.is_(False))
                .group_by(Competitor.slug)
            ).all()
            peer_product_min = min((c for _, c in counts), default=0) if counts else 0

    needs_reseed = bool(slugs) and slugs != EXPECTED_SLUGS
    needs_seed_only = not slugs
    needs_ingest = needs_reseed or needs_seed_only or peer_product_min == 0

    if needs_reseed:
        logger.warning(
            "SQLite has stale competitor slugs %s; expected %s. Dropping schema and re-seeding.",
            slugs,
            set(EXPECTED_SLUGS),
        )
        Base.metadata.drop_all(bind=engine)
        init_db()
        seed()
    elif needs_seed_only:
        logger.info("No competitors in DB; running seed.")
        seed()
    elif needs_ingest:
        logger.info("Competitor set matches but at least one peer has 0 products — re-running ingest.")

    if not needs_ingest:
        return

    if settings.use_fixtures:
        logger.info("USE_FIXTURES=true — rebuilding fixture JSON and running double ingest.")
        _run_fixture_double_ingest()
    else:
        logger.info(
            "USE_FIXTURES=false — run `python -m app.ingestion.runner` (or enqueue jobs via the worker) to pull live data."
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
