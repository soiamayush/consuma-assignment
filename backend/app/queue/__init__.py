"""Redis-backed task queue (RQ) for scraping jobs.

Why a queue at all?

- Live scrapes (browser, third-party API) are slow and flaky. Running them
  inside FastAPI request handlers blocks the event loop and ties up uvicorn
  workers.
- A queue gives us **retries**, **scheduling** (cron-like reruns), and
  **horizontal scaling** (start more ``rq worker`` containers under load).
- Same code path is used by the API endpoint and the manual CLI, so there is
  one place where failure / observability lives.

The queue is **optional**: if Redis isn't reachable, ``ingest.py`` still
supports the synchronous in-process run path it always had.
"""
