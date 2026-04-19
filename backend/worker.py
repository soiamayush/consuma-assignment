"""RQ worker entrypoint.

Run locally::

    python worker.py

In Docker, this is the ``worker`` service's CMD. It connects to ``REDIS_URL``
and processes jobs from the ``scrape`` queue using the SimpleWorker (so the
same process can run on Windows too — RQ's default ``Worker`` requires fork()).
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main() -> int:
    try:
        from redis import Redis  # type: ignore
        from rq import Queue, SimpleWorker  # type: ignore
    except ImportError:
        print("Install rq + redis first: pip install rq redis", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(
            "RQ failed to import on this platform (often rq<2.8 on Windows).\n"
            "Fix: pip install -U 'rq>=2.8,<3'   or run the worker in Docker/Linux.\n"
            f"Detail: {exc}",
            file=sys.stderr,
        )
        return 1

    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.environ.get("RQ_QUEUE", "scrape")
    conn = Redis.from_url(url)
    conn.ping()
    print(f"worker connected to {url}, listening on queue '{queue_name}'")
    worker = SimpleWorker([Queue(queue_name, connection=conn)], connection=conn)
    worker.work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
