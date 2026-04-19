# Competitor Watch — Frontend

Vite + React + TypeScript dashboard that talks to the FastAPI backend
through `/api` (dev proxy configured in `vite.config.ts`).

## Run

```powershell
npm install
npm run dev
# http://localhost:5173
```

The dev server proxies `/api` → `http://localhost:8000`.

## Build

```powershell
npm run build
npm run preview
```

## Pages

| Path | What |
| --- | --- |
| `/` | Dashboard: window selector, stat cards, top signals, brand roster, top themes. |
| `/feed` | Full signal feed with kind / brand / sort / window filters. |
| `/competitors/:slug` | Brand detail: signals, catalog grid, blog posts. |
| `/products/:id` | Product drill-down: price-history chart + snapshot table. |
| `/runs` | Ingestion run observability (auto-polling). |

## Components

- `SignalCard` — canonical ranked-signal UI with importance bar, theme
  chips, and a *Why this score?* breakdown expander.
- `PriceHistoryChart` — Recharts line chart of `price_min` over
  `captured_at`.
- `StatCard` — small labeled metric tile.
- `AppShell` — top nav + "Run ingestion" button that `POST`s to
  `/api/ingest/run`.
