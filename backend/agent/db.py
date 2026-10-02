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

import logging
import os
import time

from sqlalchemy import JSON, Boolean, Column, Float, Integer, MetaData, String, Table, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql import false as sql_false

_DEFAULT_SQLITE_URL = "sqlite:///./affinity.db"

logger = logging.getLogger(__name__)

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
    # Nullable (was NOT NULL) - a Google-only account (see
    # agent/google_auth.py / auth.login_with_google) never sets a
    # password, same "passwordless OAuth users" allowance the spec's
    # users-table schema calls for. A password/local account still always
    # gets one; only the column itself had to stop requiring it.
    Column("password_hash", String, nullable=True),
    Column("created_at", Float, nullable=False),
    # Nullable/defaulted False - there is no self-service way to become an
    # admin (no signup flag, no endpoint); promoting a user is a direct
    # database update an operator runs by hand. Gates GET
    # /admin/platform-metrics only - never affects a regular account's own
    # validations, sessions, or history.
    Column("is_admin", Boolean, nullable=False, server_default=sql_false()),
    # "local" (email/password, agent/auth.signup) or "google" (Google SSO,
    # agent/auth.login_with_google). Informational only today - login
    # itself is looked up by email regardless of provider, so a local
    # account that later signs in with the same Google-verified email is
    # simply the same row, not a separate linked identity.
    Column("auth_provider", String, nullable=False, server_default="local"),
    # Set only for a Google account, from the verified ID token's
    # "picture" claim - never accepted as raw client input.
    Column("avatar_url", String, nullable=True),
)

# One row per issued password-reset link. Only a SHA-256 hash of the token is
# stored, so a database leak does not hand out working reset links. A row is
# single-use (deleted on success) and short-lived (expires_at).
password_resets_table = Table(
    "password_resets",
    metadata,
    Column("token_hash", String, primary_key=True),
    Column("user_id", String, nullable=False, index=True),
    Column("expires_at", Float, nullable=False),
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

# Public web lookups reused across runs - see agent/web_cache.py. Distinct from
# validation_cache above, which holds whole reports for 30 minutes.
web_cache_table = Table(
    "web_cache",
    metadata,
    Column("cache_key", String, primary_key=True),
    Column("kind", String, nullable=False, index=True),
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

    url = _resolve_database_url()
    _check_persistence(url)

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
    _bootstrap_admin_emails(_engine)
    return _engine


def _resolve_database_url() -> str:
    # An empty DATABASE_URL (e.g. a Render env var that exists but whose
    # linked database was deleted) is treated the same as an unset one.
    url = os.environ.get("DATABASE_URL", "").strip() or _DEFAULT_SQLITE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


# The SQLite fallback writes to the container's own disk, which Render's
# free tier (and most other PaaS hosts without a mounted volume) wipes on
# every redeploy or restart - taking every user account, saved validation
# and admin flag with it. It used to kick in silently whenever DATABASE_URL
# was missing, so a deployment that lost its database link looked healthy
# while throwing its data away. Now it's always logged, and
# REQUIRE_PERSISTENT_DB=1 turns it into a startup failure instead: a failed
# deploy is recoverable, a silently wiped users table isn't.
def _check_persistence(url: str) -> None:
    if not url.startswith("sqlite"):
        logger.info("Database: using %s", database_backend(url))
        return

    if _is_truthy(os.environ.get("REQUIRE_PERSISTENT_DB")):
        raise RuntimeError(
            "REQUIRE_PERSISTENT_DB is set but DATABASE_URL is not a Postgres URL - refusing to start on the "
            "local SQLite fallback, whose data would be lost on the next redeploy. Set DATABASE_URL to a "
            "persistent Postgres database (see backend/.env.example)."
        )

    # Render sets RENDER=true in every service's environment.
    if _is_truthy(os.environ.get("RENDER")):
        logger.warning(
            "Database: DATABASE_URL is not set, falling back to SQLite at %s. On Render this file is NOT "
            "persistent - users, history and admin flags will be lost on the next redeploy.",
            url,
        )
    else:
        logger.info("Database: using local SQLite at %s", url)


def database_backend(url: str | None = None) -> str:
    """Which kind of database is (or would be) in use - "postgresql" or
    "sqlite" - never the URL itself, since that carries the password.
    Surfaced on GET /health so a deployment's persistence can be checked
    from outside without a shell.
    """
    resolved = url if url is not None else _resolve_database_url()
    return "sqlite" if resolved.startswith("sqlite") else resolved.split(":", 1)[0].split("+", 1)[0]


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
        if "users" in existing_tables and "auth_provider" not in existing_columns("users"):
            # Every pre-existing row predates Google SSO, so it's a local
            # (email/password) account by definition.
            conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider VARCHAR NOT NULL DEFAULT 'local'"))
        if "users" in existing_tables and "avatar_url" not in existing_columns("users"):
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR"))
        if "users" in existing_tables and engine.dialect.name == "postgresql":
            # Only Postgres can relax an existing NOT NULL in place
            # (`ALTER COLUMN ... DROP NOT NULL`); SQLite has no equivalent
            # short of rebuilding the table. A pre-existing SQLite
            # database's password_hash therefore stays NOT NULL until it's
            # recreated - an accepted gap given this codebase's own
            # documented stance that the SQLite fallback is non-persistent
            # scratch storage on every host that matters (see
            # _check_persistence above), not a database anyone migrates in
            # place. Idempotent: DROP NOT NULL on an already-nullable
            # column is a harmless no-op on every later startup.
            conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))


# Promoting an account to admin otherwise requires a direct database update
# (see users_table.is_admin above) - on a host with no interactive shell or
# SQL console (e.g. Render's free tier), that's unreachable. ADMIN_EMAILS
# gives an operator a way to do the same thing through something every
# deployment already has: an env var plus a redeploy. Runs on every engine
# creation rather than once at signup so promoting or demoting an existing
# account is just an env var edit, not a data migration - and skips
# entirely, at zero cost, on the far more common case of the var being unset.
def _bootstrap_admin_emails(engine: Engine) -> None:
    raw = os.environ.get("ADMIN_EMAILS", "")
    emails = {email.strip().lower() for email in raw.split(",") if email.strip()}
    if not emails:
        return

    inspector = inspect(engine)
    if "users" not in set(inspector.get_table_names()):
        return

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, email FROM users")).all()
        matching_ids = [row.id for row in rows if row.email.lower() in emails]
        if matching_ids:
            conn.execute(users_table.update().where(users_table.c.id.in_(matching_ids)).values(is_admin=True))


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
    "database_backend",
    "events_table",
    "get_engine",
    "jobs_table",
    "now",
    "password_resets_table",
    "reset_engine",
    "sessions_table",
    "users_table",
    "web_cache_table",
]
