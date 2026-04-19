from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()
_db_url = settings.resolved_database_url

engine = create_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if _db_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for scripts/background jobs."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _sqlite_add_column_if_missing(table: str, column: str, ddl: str) -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        names = {row[1] for row in rows}
        if column not in names:
            conn.execute(text(ddl))


def init_db() -> None:
    from . import models  # noqa: F401 ensures models are registered

    Base.metadata.create_all(bind=engine)
    _sqlite_add_column_if_missing(
        "competitors",
        "is_anchor",
        "ALTER TABLE competitors ADD COLUMN is_anchor BOOLEAN NOT NULL DEFAULT 0",
    )
    _sqlite_add_column_if_missing(
        "product_snapshots",
        "compare_at_min",
        "ALTER TABLE product_snapshots ADD COLUMN compare_at_min FLOAT",
    )
    _sqlite_add_column_if_missing(
        "product_snapshots",
        "compare_at_max",
        "ALTER TABLE product_snapshots ADD COLUMN compare_at_max FLOAT",
    )
