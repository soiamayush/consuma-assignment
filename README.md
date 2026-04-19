# Competitor Watch — Minimalist (skincare) vs peers

A small full-stack **anchor-brand** tracker: **Minimalist** (beminimalist.co)
is the company you care about; peers are **Pilgrim**, **MyGlamm**,
**Mamaearth**, **Bellavita**, **Foxtale**, and **Deconstruct** (India
clean-beauty / ingredient-led set). Most peers use public Shopify JSON
(`products.json`, blog `.atom`); **Foxtale** and **Deconstruct** are pulled via
their public `*.myshopify.com` endpoints (shopper domains differ). **MyGlamm**
has no public catalog JSON on myglamm.com — the repo includes a Shopify-shaped
snapshot so the same parser and analytics apply. Ingestion is on demand; we
detect **changes** as ranked **signals** and run **analytics** (price bands,
percentiles, cross-brand active overlap, signal velocity).

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy / SQLite
- **Frontend**: Vite / React / TypeScript / Tailwind / React Query / Recharts
- **Data source**: Shopify public `/products.json` + `/blogs/*.atom` where
  available; committed JSON for MyGlamm. Fixtures for offline demo
  (`USE_FIXTURES=true`).

## Quick start (two terminals, Windows)

1. **Copy env files once** (if you do not have them): `copy backend\.env.example backend\.env` and set `SCRAPERAPI_KEY` if you use ScraperAPI.
2. **Terminal A — API**

```powershell
cd backend
.\run.ps1
```

API listens on **http://127.0.0.1:8000** — check **http://127.0.0.1:8000/api/health**.

3. **Terminal B — UI**

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (Vite proxies `/api` → port 8000).

4. **Fill the DB with live data** (when `USE_FIXTURES=false`):

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.ingestion.runner
```

---

## Why this shape

Skincare D2C is SKU- and **ingredient-led**: hero actives (niacinamide,
retinoids, SPF) show up in titles and tags, prices move with promos, and
blogs carry reformulation / clinical narratives. The app separates **(a)
operational signals** (what changed) from **(b) portfolio analytics**
(how Minimalist’s catalog composition and price band sit vs named peers).

## Demo video (Consuma submission)

Add your **Loom** or **Google Drive** walkthrough here once recorded (2–4 minutes is enough: dashboard → signal → compare → analytics → buzz → optional Ask AI / ingestion).

**Demo link:** _paste URL tomorrow_

## Demo flow (no internet needed)

`backend/.env` and `frontend/.env` ship with safe defaults (`USE_FIXTURES=true` on the API). If you delete them, copy `backend/.env.example` to `backend/.env`.

```powershell
# 1) Backend: install deps, then run bootstrap ONCE (creates SQLite + fixtures + signals).
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.scripts.bootstrap
uvicorn app.main:app --reload --port 8000
```

Without `bootstrap`, there is no `data/watch.db` yet and the frontend will look empty. Re-run bootstrap anytime to reset demo data.

If you upgraded from an older checkout that tracked different brands, delete `backend/data/watch.db` once, then `python -m app.seed` (or `bootstrap`) so the new **Minimalist + peer** rows and `is_anchor` column line up cleanly.

```powershell
# 2) Frontend (keep the API running on port 8000 — Vite proxies /api there)
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

After `npm run dev`, the dashboard should show ranked signals from the two fixture rounds `bootstrap` ingests.

## Live mode (real public endpoints)

Set `USE_FIXTURES=false` in `backend/.env`, then:

```powershell
python -m app.seed
python -m app.ingestion.runner
```

You can also trigger a run from the UI header ("Run ingestion"), which now
**enqueues an RQ job** when Redis is reachable, and falls back to in-process
`BackgroundTasks` otherwise.

---

## Pro mode — Docker stack, real scrapers, third-party proxies

The pipeline does not assume Shopify. Each peer's `Source` row picks a
**scraper kind**, and the registry now ships:

| Kind                    | What it does                                                     |
|-------------------------|------------------------------------------------------------------|
| `shopify_products`      | Public `/products.json` (paginated, retried).                    |
| `shopify_blog_atom`     | Public Atom feed for editorial cadence.                          |
| `myglamm_internal_api`  | Real call to `api.myglamm.com` (their React app's backend).      |
| `html_listing`          | Generic HTML PLP/PDP scraper with `selectolax` + proxy fan-out.  |
| `browser_listing`       | **Playwright Chromium** — renders JS, scrolls for lazy load, can intercept XHR JSON ("session-based scraping"). |
| `fixture_*`             | Offline JSON snapshots for deterministic demos.                  |

### Third-party providers (BYO key, optional)

Set **either** in `backend/.env` (or `.env` next to `docker-compose.yml`):

```env
SCRAPERAPI_KEY=...           # api.scraperapi.com — JS render + IP rotation
SCRAPER_PROXY_URL=http://user:pass@host:port   # Bright Data / Smartproxy / own pool
SCRAPER_RENDER_JS=true       # force JS-rendered HTML through the provider
```

`html_listing`, `myglamm_internal_api`, and the Playwright browser source all
honor these — flip the env var, no code change.

### Bring up the full stack

```bash
docker compose up --build
# api      → http://localhost:8000
# frontend → http://localhost:5173 (nginx proxies /api → api:8000)
# worker   → 2 replicas pulling from Redis 'scrape' queue
# redis    → :6379
```

### Run real scrapes

```bash
# Enqueue every brand, asynchronously, on the worker pool:
docker compose exec api python -m app.scripts.enqueue --all

# One brand:
docker compose exec api python -m app.scripts.enqueue --slugs myglamm

# Re-run only the MyGlamm browser fallback (after enabling the row in seed):
docker compose exec api python -m app.scripts.enqueue --source-id 4

# Periodic — enqueue every 30 minutes (cron-equivalent for a local demo):
docker compose exec api python -m app.scripts.enqueue --all --every 30
```

`GET /api/ingest/queue/status` returns live queue depth, started/failed jobs,
and worker count, so the UI/operator can see the queue isn't backed up.

---

## Product UX

Three questions the UI answers on the dashboard:

- **What changed recently?** — stat cards (total signals, new launches,
  price drops, increases, announcements) + a ranked feed for the window.
- **What should I pay attention to first?** — each signal has an
  `importance` score (0–100) with a visible breakdown: base kind weight,
  change magnitude, recency decay (7-day halflife), brand weight, theme
  boost. Top-ranked signals float to the top of the feed.
- **Why is this item important?** — every card shows a thematic chip
  (launch / collaboration / sustainability / pricing / sold_out / …) and
  a "Why this score?" expander with the breakdown. Clicking a product
  signal drills to its full price-history chart + snapshot table.

Pages:

- `/` — **Dashboard**: window selector, stat rollups, top 8 signals, brand
  roster (anchor badge), per-brand volume bars, top themes.
- `/analytics` — **Differentiation**: median listed price by brand, signals
  in window, top actives from catalog copy, per-brand ingredient table,
  recent launches (30d).
- `/feed` — **Full signal feed**: filter by kind / brand / sort / window.
- `/competitors/:slug` — per-brand view: recent signals, full catalog grid,
  and blog posts.
- `/products/:id` — product drilldown with price-history chart and
  snapshot timeline.
- `/runs` — **Ingestion runs** observability table (auto-polling).

---

## Engineering notes

### Scraping

- Source-abstraction pattern (`BaseSource` → `ShopifyProductsSource`,
  `ShopifyBlogAtomSource`, `MyGlammApiSource`, `HtmlListingSource`,
  `BrowserListingSource`, `FixtureProductsSource`, `FixtureBlogSource`).
  Adding a new source kind is a new subclass + registry entry.
- HTTP with `tenacity` exponential retries on 5xx/429/transport errors.
- Provider-aware fetch (`scrapers/proxy.py`) — direct → generic proxy →
  ScraperAPI, picked at runtime from env vars.
- Browser source uses Playwright with **XHR interception** (read what the SPA
  would have rendered) and a DOM fallback with scroll-driven lazy load.
- Per-item parse errors are logged and skipped, not fatal to the run.

### Queue / workers

- `app/queue/jobs.py` exposes pure functions (`scrape_all`,
  `scrape_competitor`, `scrape_source`) so the same code path runs from the
  HTTP endpoint, the CLI (`app.scripts.enqueue`), and the RQ worker
  (`worker.py`).
- Workers use `SimpleWorker` so the same image runs on Linux containers and
  on Windows dev boxes (no `fork()` requirement).
- `docker-compose.yml` ships **2 worker replicas** by default — bump
  `deploy.replicas` to scale horizontally.

### Storage

- `Product` is canonical per `(competitor, external_id)`.
- `ProductSnapshot` is append-only; a new row is written only when the
  content hash changes (title + price + availability + variant count).
- `Signal` rows are de-duped via a stable `dedupe_key` so re-ingests are
  idempotent.

### Intelligence

- **Theme classifier** (`intelligence/themes.py`): rule-based, ordered
  keyword matcher. Transparent, easy to extend, no model key required.
- **Change detection** (`intelligence/change_detection.py`): compares
  current vs previous snapshot and emits signals with computed
  importance. A catalog-surge detector fires once per day per brand when
  ≥ 5 new products show up in a single run.
- **Importance scoring** (`intelligence/scoring.py`): a small, explainable
  formula with every term stored on the signal row. Swappable for an
  ML-based ranker later without changing the API.

### Real-world concerns covered

- Pagination, retries, dedupe, incremental updates, validation,
  parser/source abstraction, content-hash snapshots, observability rows,
  and a fixtures mode for deterministic demos.

---

## Repo layout

```
.
├── backend/               # FastAPI + scraper + intelligence
│   ├── app/
│   ├── requirements.txt
│   └── README.md          # backend-specific details + API reference
├── frontend/              # Vite + React + TypeScript dashboard
│   ├── src/
│   └── package.json
└── README.md              # ← you are here
```

See `backend/README.md` for deeper architecture details and the full API
surface. OpenAPI live at `http://localhost:8000/docs`.

---

## Assumptions & trade-offs

- I kept the theme classifier rule-based; an embedding-based classifier or
  an LLM pass would be a one-file swap but isn't necessary for the
  signals I generate.
- I use `/products.json` (public, stable, documented) rather than parsing
  rendered HTML. It's friendlier to the sites and less likely to break.
  A few brands in the wild (Everlane, Rothy's) don't run on Shopify;
  they'd need their own `BaseSource` subclass.
- Storage is SQLite for one-command local running. Swapping to Postgres
  is a `DATABASE_URL` change.
- The importance formula is deliberately simple and explainable so an
  analyst can eyeball the ranking and tell *why* an item is up top.
