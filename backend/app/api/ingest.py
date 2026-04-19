from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, session_scope
from ..ingestion.runner import run_all
from ..models import IngestionRun
from ..queue.connection import get_queue
from ..queue.jobs import scrape_all, scrape_competitor
from ..schemas import IngestionRunOut, IngestResult

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    slugs: Optional[list[str]] = None


def _run_in_background(slugs: Optional[list[str]]) -> None:
    with session_scope() as db:
        run_all(db, competitor_slugs=slugs)


@router.post("/run", response_model=dict)
def trigger_run(
    background_tasks: BackgroundTasks,
    body: Optional[IngestRequest] = Body(default=None),
    sync: bool = False,
    use_queue: bool = Query(
        False,
        description=(
            "If true, enqueue on Redis/RQ (requires a running worker). "
            "Default false so local dev works when Redis is up but no worker is running."
        ),
    ),
    db: Session = Depends(get_db),
):
    """Trigger an ingestion run.

    - ``sync=true``       → run inline and return the full ``IngestResult``.
    - ``use_queue=true``  → enqueue jobs on the **Redis (RQ) queue** so a
      separate worker process executes them. Falls back to ``BackgroundTasks``
      (in-process) if Redis isn't reachable or ``use_queue`` is false.
    """
    slugs = body.slugs if body else None
    if sync:
        runs = run_all(db, competitor_slugs=slugs)
        db.commit()
        return IngestResult(
            runs=[IngestionRunOut.model_validate(r) for r in runs],
            total_signals=sum(r.signals_created for r in runs),
        ).model_dump()

    queue_note: str | None = None
    if use_queue:
        queue = get_queue()
        if queue is not None:
            if slugs:
                job_ids = [queue.enqueue(scrape_competitor, s, job_timeout=600).id for s in slugs]
            else:
                job_ids = [queue.enqueue(scrape_all, job_timeout=1800).id]
            return {"queued": True, "via": "rq", "slugs": slugs, "job_ids": job_ids}
        queue_note = (
            "RQ/Redis queue was requested but is unavailable (Redis down, old rq<2.8 on Windows, or "
            "missing packages). Ingestion runs in-process — upgrade `pip install -U 'rq>=2.8'` or "
            "run `docker compose up` (api + worker + redis) for a full queue stack."
        )

    background_tasks.add_task(_run_in_background, slugs)
    out: dict[str, object] = {"queued": True, "via": "background_tasks", "slugs": slugs}
    if queue_note:
        out["note"] = queue_note
    return out


@router.get("/queue/status")
def queue_status():
    """Live RQ queue depth + worker count, or ``{enabled: false}`` if Redis is down."""
    queue = get_queue()
    if queue is None:
        return {"enabled": False}
    try:
        from rq import Worker  # type: ignore

        workers = Worker.all(connection=queue.connection)
    except Exception:
        workers = []
    return {
        "enabled": True,
        "name": queue.name,
        "depth": queue.count,
        "started_jobs": queue.started_job_registry.count,
        "failed_jobs": queue.failed_job_registry.count,
        "scheduled_jobs": queue.scheduled_job_registry.count,
        "workers": len(workers),
    }


@router.get("/runs", response_model=list[IngestionRunOut])
def list_runs(
    response: Response,
    limit: int = Query(30, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(IngestionRun.id))) or 0
    runs = list(
        db.scalars(
            select(IngestionRun)
            .order_by(IngestionRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [IngestionRunOut.model_validate(r) for r in runs]
