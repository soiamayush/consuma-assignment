# Competitor Watch — Backend

FastAPI + SQLAlchemy + SQLite. Scrapes public Shopify endpoints for
minimalist D2C brands, detects changes, surfaces ranked signals.

## Quickstart

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # optional if `backend/.env` is missing
```

### Run the API (required for the Vite frontend)

The UI calls `/api/...` on **port 5173**; Vite’s dev server **proxies** those requests to **http://127.0.0.1:8000**. You must keep the backend running in a **second terminal**:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1   # if you use a venv
.\run.ps1
# or:  python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/docs to confirm it is up.

If you see **500** errors in the browser Network tab for `/api/...`, the usual causes are: backend not running on 8000, or the SQLite file path was wrong (fixed: `.env` and DB path are resolved relative to the `backend/` folder regardless of cwd).

### One-command demo (no internet required)

```powershell
python -m app.scripts.bootstrap
uvicorn app.main:app --reload --port 8000
```

The bootstrap script:
1. Generates round-1 fixtures (realistic Shopify-shaped JSON).
2. Seeds five brands + their fixture sources.
3. Runs ingestion (creates products, snapshots, LAUNCH signals).
4. Generates round-2 fixtures (price changes, new launches, a sold-out item,
   a fresh blog post on some brands).
5. Runs ingestion again — this run generates PRICE_DROP / PRICE_INCREASE /
   OUT_OF_STOCK / PRODUCT_LAUNCH / BLOG_POST / CATALOG_SURGE signals.

### Live mode (hit the real Shopify endpoints)

```powershell
# .env
# USE_FIXTURES=false

python -m app.seed
python -m app.ingestion.runner
uvicorn app.main:app --reload --port 8000
```

To target specific brands:

```powershell
python -m app.ingestion.runner --slugs allbirds kotn
```

## API highlights

| Method | Path | What |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/competitors` | **Peer brands only** by default (`include_anchor=false`). Pass `?include_anchor=true` for the full watch list. |
| `GET` | `/api/competitors/anchor` | The single anchor brand (Minimalist) with rollups |
| `GET` | `/api/competitors/{slug}` | Brand detail |
| `GET` | `/api/products?competitor=…&q=…` | Products |
| `GET` | `/api/products/{id}` | Product with full snapshot history |
| `GET` | `/api/signals?kind=…&competitor=…&sort=importance|recent&window_days=…` | Ranked signal feed |
| `GET` | `/api/dashboard/summary?window_days=14` | Dashboard rollup |
| `GET` | `/api/blog-posts?competitor=…` | Recent posts |
| `POST` | `/api/ingest/run` | Trigger a run (background by default, `?sync=true` to await) |
| `GET` | `/api/ingest/runs` | Last 30 ingestion runs (observability) |

OpenAPI docs live at `http://localhost:8000/docs`.

## Architecture

```
app/
├── config.py              # pydantic-settings, .env, USE_FIXTURES toggle
├── db.py                  # SQLAlchemy engine / session / init_db()
├── models.py              # Competitor, Source, IngestionRun, Product,
│                          # ProductSnapshot, BlogPost, Signal
├── schemas.py             # Pydantic response models
├── time_utils.py          # naive-UTC helpers (consistent with SQLite)
├── scrapers/
│   ├── base.py            # BaseSource, httpx helper w/ tenacity retries
│   ├── shopify_products.py  # /products.json paginated source
│   ├── shopify_blog.py    # Atom feed source
│   ├── fixture.py         # offline fixture sources (same parser)
│   └── registry.py        # kind -> source class
├── ingestion/
│   └── runner.py          # orchestrates fetch → validate → dedupe → snapshot
│                          # → change detection → signal generation
├── intelligence/
│   ├── themes.py          # rule-based theme classifier
│   ├── scoring.py         # importance score (base · magnitude · recency
│   │                      # · brand_weight + theme_boost, 0..1)
│   └── change_detection.py  # compares snapshots, emits Signals with
│                          # stable dedupe keys (idempotent re-runs)
├── api/                   # FastAPI routers
├── seed.py                # 5 minimalist D2C brands + sources (live + fixture maps)
└── scripts/
    ├── make_fixtures.py   # round-1 / round-2 fixture generator
    └── bootstrap.py       # end-to-end local demo runner
```

## Scraper concerns we handle

- **Pagination** — Shopify `/products.json` uses `?page=N&limit=250`; we stop on
  an empty page or when a page returns fewer than `limit`.
- **Retries** — `tenacity` exponential backoff on `5xx`/`429`/transport errors
  (3 attempts, 1–10s backoff).
- **Parser/source abstraction** — `BaseSource` exposes `fetch_products` /
  `fetch_blog_posts`; adding a new brand or a non-Shopify source is a new
  subclass registered in `registry.py`.
- **Validation** — `_valid_product`/`_valid_blog` in `runner.py` drop items with
  missing ids/titles; individual parser errors don't abort a run.
- **Dedup + incremental updates** — products are upserted by
  `(competitor_id, external_id)`; we only write a new `ProductSnapshot` when
  the content hash changes; blog posts are upserted by `(competitor_id, external_id)`.
- **Change detection** — price delta ≥ 3%, availability flips, new products,
  removed products, catalog surges (≥ 5 new in one run).
- **Idempotent signals** — `Signal.dedupe_key` is a SHA1 of the core change
  identity, preventing duplicates on repeated runs.
- **Observability** — every run records `items_seen / new / changed / signals_created`
  on `IngestionRun`; exposed at `/api/ingest/runs`.

## Intelligence layer

`Signal.importance` is a 0..1 score computed at write time as:

```
final = base_kind_weight
      * (0.55 + 0.45 * magnitude)
      * (0.50 + 0.50 * recency_halflife_7d)
      * (0.60 + 0.40 * brand_weight)
      + theme_boost(launch | collab | sustainability | expansion | …)
```

The per-signal `delta.score_breakdown` is persisted so the UI can show
*"Why this score?"* — every term is visible.

## Re-running + incremental behavior

Everything is idempotent. You can re-run ingestion safely:

- Same products are matched by `external_id`.
- Snapshots only written when content changes.
- Signals de-duped on `dedupe_key`.
- For a fun demo loop, alternate `make_fixtures --round 1` / `--round 2` and
  re-run ingestion — you'll see price drops resolve and new launches appear.
