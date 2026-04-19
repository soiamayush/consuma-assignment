"""Job functions invoked by the RQ worker.

These are *plain* functions (no FastAPI request context) so they can be
serialised and re-executed by any worker process. Each one opens its own DB
session via ``session_scope`` and commits when done.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from ..db import session_scope
from ..ingestion.runner import run_all, run_source
from ..models import Source

logger = logging.getLogger(__name__)


def scrape_competitor(slug: str) -> dict:
    """Run all enabled sources for one competitor slug. Returns a stats summary."""
    logger.info("queue job: scrape_competitor slug=%s", slug)
    with session_scope() as db:
        runs = run_all(db, competitor_slugs=[slug])
    return {
        "slug": slug,
        "runs": [
            {
                "source_id": r.source_id,
                "status": r.status,
                "items_seen": r.items_seen,
                "items_new": r.items_new,
                "items_changed": r.items_changed,
                "signals_created": r.signals_created,
                "error": r.error,
            }
            for r in runs
        ],
    }


def scrape_source(source_id: int) -> dict:
    """Run a single Source row by id. Useful for retrying a failed scraper."""
    logger.info("queue job: scrape_source id=%s", source_id)
    with session_scope() as db:
        src = db.scalar(select(Source).where(Source.id == source_id))
        if not src:
            return {"source_id": source_id, "status": "missing"}
        run = run_source(db, src)
        db.commit()
        return {
            "source_id": source_id,
            "status": run.status,
            "items_seen": run.items_seen,
            "items_new": run.items_new,
            "items_changed": run.items_changed,
            "signals_created": run.signals_created,
            "error": run.error,
        }


def scrape_all() -> dict:
    """Full sweep across every enabled source."""
    logger.info("queue job: scrape_all")
    with session_scope() as db:
        runs = run_all(db)
    return {"runs": len(runs), "errors": sum(1 for r in runs if r.status != "ok")}
