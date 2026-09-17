"""Bounded, database-backed validation and chat session storage.

Same public interface (create_session/get_session/append_turn/
reserve_chat_request/clear_sessions) as before this was backed by a
process-local dict, so main.py and chat_graph.py needed no changes -
only the storage underneath moved to db.py's `sessions` table, which
survives a restart and is shared across however many backend instances
are running.
"""

import uuid

from sqlalchemy import delete, select

from .db import get_engine, now, sessions_table

_SESSION_TTL_SECONDS = 2 * 60 * 60
_MAX_SESSIONS = 200
_MAX_TURNS = 12
_CHAT_WINDOW_SECONDS = 60
_MAX_CHAT_REQUESTS_PER_WINDOW = 6


def _prune(conn) -> None:
    cutoff = now() - _SESSION_TTL_SECONDS
    conn.execute(delete(sessions_table).where(sessions_table.c.updated_at < cutoff))

    overflow = conn.execute(select(sessions_table.c.id).order_by(sessions_table.c.updated_at.desc())).scalars().all()
    if len(overflow) > _MAX_SESSIONS:
        stale_ids = overflow[_MAX_SESSIONS:]
        conn.execute(delete(sessions_table).where(sessions_table.c.id.in_(stale_ids)))


def _row_to_session(row) -> dict:
    return {
        "context": row.context,
        "history": row.history,
        "chatRequestTimes": row.chat_request_times,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def create_session(context: dict) -> str:
    session_id = str(uuid.uuid4())
    timestamp = now()
    engine = get_engine()
    with engine.begin() as conn:
        _prune(conn)
        conn.execute(
            sessions_table.insert().values(
                id=session_id,
                context=context,
                history=[],
                chat_request_times=[],
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return session_id


def get_session(session_id: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        _prune(conn)
        row = conn.execute(select(sessions_table).where(sessions_table.c.id == session_id)).first()
        if row is None:
            return None
        conn.execute(sessions_table.update().where(sessions_table.c.id == session_id).values(updated_at=now()))
        return _row_to_session(row)


def append_turn(session_id: str, message: str, reply: str) -> bool:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(sessions_table).where(sessions_table.c.id == session_id)).first()
        if row is None:
            return False
        history = (row.history or []) + [{"message": message, "reply": reply}]
        history = history[-_MAX_TURNS:]
        conn.execute(
            sessions_table.update()
            .where(sessions_table.c.id == session_id)
            .values(history=history, updated_at=now())
        )
        return True


def reserve_chat_request(session_id: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        _prune(conn)
        row = conn.execute(select(sessions_table).where(sessions_table.c.id == session_id)).first()
        if row is None:
            raise KeyError("Session not found or expired.")

        current = now()
        cutoff = current - _CHAT_WINDOW_SECONDS
        recent = [timestamp for timestamp in (row.chat_request_times or []) if timestamp >= cutoff]
        if len(recent) >= _MAX_CHAT_REQUESTS_PER_WINDOW:
            raise RuntimeError("Chat rate limit exceeded.")

        recent.append(current)
        conn.execute(
            sessions_table.update()
            .where(sessions_table.c.id == session_id)
            .values(chat_request_times=recent, updated_at=current)
        )


def clear_sessions() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(sessions_table))
