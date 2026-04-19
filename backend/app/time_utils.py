"""Centralized time helpers.

SQLAlchemy `DateTime()` columns in this project store naive UTC. We standardize
on naive UTC everywhere the DB is involved so comparisons never raise
`TypeError: can't compare offset-naive and offset-aware datetimes`.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Naive UTC 'now' suitable for SQLAlchemy DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
