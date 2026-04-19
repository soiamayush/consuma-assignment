"""One-shot local bootstrap for demos.

Runs:
  1. generate round-1 fixtures
  2. seed competitors + fixture sources
  3. run ingestion
  4. generate round-2 fixtures (price changes, new launches, sold-out, new blog posts)
  5. run ingestion again

After this you can `uvicorn app.main:app` and the dashboard has meaningful data.
Forces USE_FIXTURES=true so no network calls happen.
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ["USE_FIXTURES"] = "true"

    # Import after env var set so Settings picks it up.
    from ..config import get_settings
    from ..db import init_db, session_scope
    from ..ingestion.runner import run_all
    from ..seed import seed
    from .make_fixtures import main as make_fixtures_main

    get_settings.cache_clear()  # type: ignore[attr-defined]

    print("==> Round 1 fixtures")
    sys.argv = ["make_fixtures", "--round", "1"]
    make_fixtures_main()

    print("\n==> Seed")
    seed()

    print("\n==> Ingest round 1")
    init_db()
    with session_scope() as db:
        runs = run_all(db)
        for r in runs:
            print(f"  [{r.status}] source={r.source_id} seen={r.items_seen} "
                  f"new={r.items_new} changed={r.items_changed} signals={r.signals_created}")

    print("\n==> Round 2 fixtures (simulating real-world changes)")
    sys.argv = ["make_fixtures", "--round", "2"]
    make_fixtures_main()

    print("\n==> Ingest round 2")
    with session_scope() as db:
        runs = run_all(db)
        for r in runs:
            print(f"  [{r.status}] source={r.source_id} seen={r.items_seen} "
                  f"new={r.items_new} changed={r.items_changed} signals={r.signals_created}")

    print("\nDone. Start the API with:  uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
