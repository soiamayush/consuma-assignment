"""Single place to construct the Redis connection + RQ queue.

Reads ``REDIS_URL`` from the environment (default ``redis://localhost:6379/0``).
Returns ``None`` if Redis isn't reachable so the API can fall back to inline
execution without crashing in dev.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.environ.get("RQ_QUEUE", "scrape")


def get_queue():  # -> Optional[rq.Queue]
    try:
        from redis import Redis  # type: ignore
        from rq import Queue  # type: ignore
    except ImportError:
        logger.info("rq/redis not installed; queue disabled")
        return None
    except ValueError as exc:
        # RQ 1.x: rq/scheduler.py calls get_context("fork") at import time — fails on
        # Windows (and some Python 3.14 builds). RQ 2.x catches this; until then we
        # disable the queue instead of crashing the API with 500.
        logger.warning("rq import failed on this platform (%s); queue disabled", exc)
        return None
    try:
        conn = Redis.from_url(REDIS_URL, socket_connect_timeout=1.5)
        conn.ping()
    except Exception as exc:
        logger.warning("redis unreachable at %s (%s); queue disabled", REDIS_URL, exc)
        return None
    return Queue(QUEUE_NAME, connection=conn, default_timeout=600)


def get_redis() -> Optional[object]:
    try:
        from redis import Redis  # type: ignore
    except ImportError:
        return None
    try:
        conn = Redis.from_url(REDIS_URL, socket_connect_timeout=1.5)
        conn.ping()
        return conn
    except Exception:
        return None
