"""Manual queue driver — enqueue scrape jobs from the CLI.

Usage::

    # All competitors
    python -m app.scripts.enqueue --all

    # Specific competitor (one or many)
    python -m app.scripts.enqueue --slugs minimalist pilgrim

    # A specific Source row (handy when you want to rerun ONLY MyGlamm's
    # browser fallback after the JSON API failed)
    python -m app.scripts.enqueue --source-id 12

    # Periodic schedule: enqueue every N minutes (uses rq-scheduler if installed,
    # otherwise sleeps in-process — keep the process running).
    python -m app.scripts.enqueue --all --every 30

The script targets the same RQ queue the worker pulls from, so anything you
enqueue here will be executed by the next available worker (locally or in the
docker-compose stack).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from ..queue.connection import get_queue
from ..queue.jobs import scrape_all, scrape_competitor, scrape_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _enqueue_once(args, queue) -> list[str]:
    if args.source_id:
        return [queue.enqueue(scrape_source, args.source_id, job_timeout=600).id]
    if args.slugs:
        return [queue.enqueue(scrape_competitor, s, job_timeout=600).id for s in args.slugs]
    if args.all:
        return [queue.enqueue(scrape_all, job_timeout=1800).id]
    raise SystemExit("Pass --all, --slugs, or --source-id.")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true", help="Enqueue scrape_all (every enabled source)")
    p.add_argument("--slugs", nargs="*", help="Specific competitor slugs to scrape")
    p.add_argument("--source-id", type=int, help="Re-run a single Source row by primary key")
    p.add_argument("--every", type=int, help="Repeat enqueue every N minutes (foreground loop)")
    args = p.parse_args()

    queue = get_queue()
    if queue is None:
        print("Redis/RQ unavailable. Set REDIS_URL or run docker-compose up.", file=sys.stderr)
        return 2

    if args.every:
        logger.info("Enqueuing every %d minute(s). Ctrl-C to stop.", args.every)
        while True:
            ids = _enqueue_once(args, queue)
            logger.info("enqueued %d job(s) ids=%s", len(ids), ids)
            time.sleep(args.every * 60)

    ids = _enqueue_once(args, queue)
    logger.info("enqueued %d job(s) ids=%s", len(ids), ids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
