"""Shared database layer for everything that used to live only in a
process-local dict: validation sessions (session_store.py), background
validation jobs (job_store.py), and the /validate response cache (main.py).

Backed by Postgres in production (DATABASE_URL set on Render) and SQLite
everywhere else (local dev, tests) so nothing here requires a live database
just to run the test suite. Same TTL + max-row-count pruning philosophy the
in-memory stores already used, just enforced with SQL instead of dict
bookkeeping - and now the data survives a restart and is shared across
however many backend instances are running, which the in-memory version
never could be.
"""

import os
import time

from sqlalchemy import JSON, Column, Float, MetaData, String, Table, create_engine
from sqlalchemy.engine import Engine

_DEFAULT_SQLITE_URL = "sqlite:///./affinity.db"

metadata = MetaData()

sessions_table = Table(
    "sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("context", JSON, nullable=False),
    Column("history", JSON, nullable=False),
    Column("chat_request_times", JSON, nullable=False),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False, index=True),
)

jobs_table = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("result", JSON, nullable=True),
    Column("error", String, nullable=True),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False, index=True),
)

cache_table = Table(
    "validation_cache",
    metadata,
    Column("cache_key", String, primary_key=True),
    Column("data", JSON, nullable=False),
    Column("cached_at", Float, nullable=False, index=True),
)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Lazily builds the shared engine so importing this module never
    requires DATABASE_URL to already be set (e.g. at collection time in
    tests) - only actually connecting does.

    Render's Postgres add-on hands out a `postgres://` URL; SQLAlchemy 2.x
    only recognizes the `postgresql://` scheme, so that prefix is rewritten
    here rather than requiring every deployment to remember to do it.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE_URL)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}

    # Pool sizing only applies to Postgres - SQLite (local dev/tests) uses
    # SQLAlchemy's own SingletonThreadPool/NullPool automatically and
    # ignores these. Configurable via env vars rather than hardcoded so the
    # same code works whether this runs as one instance or several: each
    # instance opens its own pool, so pool_size should be set with
    # (instances x pool_size) comfortably under the database plan's max
    # connection count, not against a single instance in isolation.
    # pool_pre_ping avoids handing out a connection Render's Postgres has
    # since dropped for being idle; pool_recycle proactively retires
    # connections before that happens. pool_timeout makes exhaustion fail
    # fast with a clear error instead of a hung request.
    pool_kwargs = (
        {
            "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.environ.get("DB_POOL_MAX_OVERFLOW", "5")),
            "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT_SECONDS", "10")),
            "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800")),
        }
        if not url.startswith("sqlite")
        else {}
    )

    _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, **pool_kwargs)
    metadata.create_all(_engine)
    return _engine


def reset_engine() -> None:
    """Test-only: drop the cached engine so a later get_engine() call picks
    up a changed DATABASE_URL (e.g. a test pointing at a throwaway sqlite
    file) instead of reusing whatever was created first.
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def now() -> float:
    return time.time()


__all__ = [
    "cache_table",
    "get_engine",
    "jobs_table",
    "now",
    "reset_engine",
    "sessions_table",
]
