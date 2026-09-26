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
from .decision_history import append_decision as _append_decision

_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
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
        "decisions": row.decisions or [],
    }


def create_session(context: dict, user_id: str | None = None) -> str:
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
                user_id=user_id,
                decisions=[],
            )
        )
    return session_id


def list_sessions_for_user(user_id: str, limit: int = 50) -> list[dict]:
    """Powers GET /me/history - the signed-in equivalent of the device-local
    history frontend/src/lib/history.js keeps for anonymous use. Only
    surfaces the fields a history list needs (idea/targetCustomer/dates),
    not the full context, since callers who want the rest already have
    GET /reports/{sessionId} for that.
    """
    engine = get_engine()
    with engine.begin() as conn:
        _prune(conn)
        rows = conn.execute(
            select(sessions_table)
            .where(sessions_table.c.user_id == user_id)
            .order_by(sessions_table.c.created_at.desc())
            .limit(limit)
        ).all()
    return [
        {
            "sessionId": row.id,
            "idea": (row.context or {}).get("idea", ""),
            "targetCustomer": (row.context or {}).get("targetCustomer", ""),
            "createdAt": row.created_at,
        }
        for row in rows
    ]


def claim_session(session_id: str, user_id: str) -> bool:
    """Attaches an anonymous validation (started before sign-in) to the
    account that just signed in, so it shows up in GET /me/history instead
    of being stuck device-local forever. Only claims a session that has no
    owner yet - one already tied to a *different* account (e.g. a stale
    sessionId reused across browser tabs/accounts) is left alone rather
    than reassigned.
    """
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(sessions_table).where(sessions_table.c.id == session_id)).first()
        if row is None:
            return False
        if row.user_id is not None:
            return row.user_id == user_id
        conn.execute(
            sessions_table.update().where(sessions_table.c.id == session_id).values(user_id=user_id, updated_at=now())
        )
        return True


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
    """Also runs the message through decision_history.append_decision -
    the "lightweight pass over the chat transcript" Track G.1 calls for,
    done inline here rather than as a separate pass so a pivot is recorded
    in the same transaction as the turn that contained it.
    """
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(sessions_table).where(sessions_table.c.id == session_id)).first()
        if row is None:
            return False
        history = (row.history or []) + [{"message": message, "reply": reply}]
        history = history[-_MAX_TURNS:]
        decisions = _append_decision(row.decisions or [], message, now())
        conn.execute(
            sessions_table.update()
            .where(sessions_table.c.id == session_id)
            .values(history=history, decisions=decisions, updated_at=now())
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
