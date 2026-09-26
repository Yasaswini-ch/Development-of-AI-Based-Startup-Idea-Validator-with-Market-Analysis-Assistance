"""Database-backed operational event log for GET /admin/platform-metrics.

agent/metrics.py's in-process counters answer "what's the total right now"
but reset to zero on every restart and can't answer "how did this trend
over the last 30 days." This is the durable counterpart: every row is one
observation (a node's latency sample, which model served an LLM call, a
cache hit/miss, a node failure, an idea's category, an email delivery
outcome) with a type, an optional node name, a small JSON detail blob, and
a timestamp - see db.py's events_table for the schema and why one flexible
table covers all of these instead of a table per metric.

Aggregation (average latency, model-usage split, daily volume, ...)
happens in Python over rows fetched from a bounded time window, not in
SQL - GET /admin/platform-metrics is an infrequent, admin-only read, not a
hot path, and there is no portable way to query a JSON column's inner
fields across both SQLite and Postgres without dialect-specific SQL.
"""

import time

from sqlalchemy import delete, select

from .db import events_table, get_engine, now

# Same TTL-pruning shape as session_store.py/job_store.py, chosen for the
# widest window any platform-metrics chart needs (90d) plus headroom - a
# node runs on every validation, so this table's write volume is much
# higher than sessions/jobs and unbounded retention isn't appropriate here.
_EVENT_TTL_SECONDS = 90 * 24 * 60 * 60
_MAX_EVENTS = 200_000


def _prune(conn) -> None:
    cutoff = now() - _EVENT_TTL_SECONDS
    conn.execute(delete(events_table).where(events_table.c.created_at < cutoff))

    overflow = conn.execute(select(events_table.c.id).order_by(events_table.c.created_at.desc())).scalars().all()
    if len(overflow) > _MAX_EVENTS:
        stale_ids = overflow[_MAX_EVENTS:]
        conn.execute(delete(events_table).where(events_table.c.id.in_(stale_ids)))


def record(event_type: str, node: str | None = None, detail: dict | None = None) -> None:
    """Append one event. Never raises into the caller - every call site is
    instrumentation wrapped around real pipeline/request work, and losing
    one metrics row must never be the reason a validation request fails.
    """
    try:
        engine = get_engine()
        with engine.begin() as conn:
            # Pruning on every write (like session_store/job_store) rather
            # than on a schedule - simplest option, and cheap relative to
            # the LLM calls most of these events are recorded alongside.
            _prune(conn)
            conn.execute(
                events_table.insert().values(
                    type=event_type,
                    node=node,
                    detail=detail,
                    created_at=now(),
                )
            )
    except Exception:
        pass


def query(
    event_type: str,
    since: float | None = None,
    node: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Matching rows, newest first, as [{"type", "node", "detail",
    "createdAt"}, ...].
    """
    engine = get_engine()
    stmt = select(events_table).where(events_table.c.type == event_type)
    if since is not None:
        stmt = stmt.where(events_table.c.created_at >= since)
    if node is not None:
        stmt = stmt.where(events_table.c.node == node)
    stmt = stmt.order_by(events_table.c.created_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)

    with engine.begin() as conn:
        rows = conn.execute(stmt).all()

    return [
        {"type": row.type, "node": row.node, "detail": row.detail, "createdAt": row.created_at}
        for row in rows
    ]


def window_start(days: int) -> float:
    """Convenience for callers building a `since` cutoff for `query()`."""
    return time.time() - days * 24 * 60 * 60


def clear() -> None:
    """Test-only - production has no reason to clear this mid-process."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(events_table))


__all__ = ["clear", "query", "record", "window_start"]
