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

from sqlalchemy import JSON, Boolean, Column, Float, Integer, MetaData, String, Table, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql import false as sql_false

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
    # Nullable: a validation is still allowed with no signed-in user (the
    # app's whole prior history had no accounts at all - see main.py's own
    # "no accounts to scope one to" comment on CompareReportsRequest). Only
    # set when the request that created this session carried a valid auth
    # token, so an owned session can be listed back via GET /me/history.
    Column("user_id", String, nullable=True, index=True),
    # Advisor Decision History (Track G.1) - a lightweight, deterministic
    # log of pivots/decisions detected in the chat transcript (see
    # agent/decision_history.py). Nullable/defaulted to [] at insert time
    # for the same reason chat_request_times is: every session gets one,
    # signed-in or not, chat used yet or not.
    Column("decisions", JSON, nullable=True),
)

# Sessions are TTL-pruned (session_store._prune, 7 days / 200-row cap) since
# they were designed as a bounded cache, not permanent storage - a signed-in
# user's "board" is therefore only as durable as that TTL today. Extending
# retention for owned sessions specifically is a deliberate follow-up, not
# done here, since it's a real resource/cost tradeoff (unbounded per-user
# storage) rather than a pure auth concern.
users_table = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("email", String, nullable=False, unique=True, index=True),
    Column("password_hash", String, nullable=False),
    Column("created_at", Float, nullable=False),
    # Nullable/defaulted False - there is no self-service way to become an
    # admin (no signup flag, no endpoint); promoting a user is a direct
    # database update an operator runs by hand. Gates GET
    # /admin/platform-metrics only - never affects a regular account's own
    # validations, sessions, or history.
    Column("is_admin", Boolean, nullable=False, server_default=sql_false()),
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

# Append-only operational log backing GET /admin/platform-metrics - the
# in-memory-only counters in agent/metrics.py answer "what's the total
# right now" but can't answer "how did this trend over the last 30 days"
# and reset to zero on every restart. One flexible table (rather than a
# separate one per metric) since every row this needs to record - a node's
# latency sample, which model served an LLM call, a cache hit/miss, a
# node failure, an idea's category, an email delivery outcome - is the
# same shape: a type, an optional node name, and a small JSON detail blob,
# timestamped. agent/events.py is the only writer/reader; nothing else
# should query this table directly.
events_table = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type", String, nullable=False, index=True),
    Column("node", String, nullable=True, index=True),
    Column("detail", JSON, nullable=True),
    Column("created_at", Float, nullable=False, index=True),
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
    _migrate_missing_columns(_engine)
    return _engine


# `metadata.create_all()` only creates tables that don't exist yet - it never
# alters a table that's already there, so adding `sessions.user_id` to the
# Table() definition above did nothing to Render's existing production
# `sessions` table (or anyone's pre-existing local affinity.db). Without
# this, every /validate call - not just authenticated ones, since
# _create_validation_session always writes a user_id column now - would
# start failing in any environment with a pre-auth database. This is a
# minimal, hand-rolled substitute for a real migration tool (no Alembic in
# this project): it only ever adds a column that's missing, on the two
# tables that changed shape after already shipping, and is a no-op (one
# cheap introspection query) once a database is up to date.
def _migrate_missing_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    def existing_columns(table_name: str) -> set[str]:
        return {col["name"] for col in inspector.get_columns(table_name)}

    with engine.begin() as conn:
        if "sessions" in existing_tables and "user_id" not in existing_columns("sessions"):
            conn.execute(text("ALTER TABLE sessions ADD COLUMN user_id VARCHAR"))
            # IF NOT EXISTS is supported by both SQLite (3.8+) and Postgres -
            # a fresh database gets this index from the Column(index=True)
            # declaration via create_all() instead; this only covers the
            # migrated-in-place case where that never ran.
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)"))
        if "sessions" in existing_tables and "decisions" not in existing_columns("sessions"):
            conn.execute(text("ALTER TABLE sessions ADD COLUMN decisions JSON"))
        if "users" in existing_tables and "is_admin" not in existing_columns("users"):
            # A DEFAULT is required here (not just NOT NULL) - SQLite
            # rejects ADD COLUMN ... NOT NULL on a non-empty table
            # otherwise, and every existing user row must resolve to
            # "not admin" rather than NULL either way.
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))


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
    "events_table",
    "get_engine",
    "jobs_table",
    "now",
    "reset_engine",
    "sessions_table",
    "users_table",
]
