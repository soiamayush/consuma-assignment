"""Wipe all ingested products + snapshots + product-linked signals, then re-seed competitors.

Use when fixture/live mixes left impossible price history (e.g. $31 next to ₹649).

Run from ``backend``::

    python -m app.scripts.clear_product_catalog
    python -m app.ingestion.runner

Keeps ``competitors``, ``sources``, and blog rows; only clears catalog + product signals.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete

from ..db import init_db, session_scope
from ..models import Product, Signal

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    with session_scope() as db:
        n_sig = db.execute(delete(Signal).where(Signal.entity_type == "product")).rowcount or 0
        n_prod = db.execute(delete(Product)).rowcount or 0
        logger.info("deleted product signals=%s products=%s (snapshots cascade)", n_sig, n_prod)
    print("Done. Run: python -m app.ingestion.runner   (and USE_FIXTURES=false for live Shopify)")


if __name__ == "__main__":
    main()
