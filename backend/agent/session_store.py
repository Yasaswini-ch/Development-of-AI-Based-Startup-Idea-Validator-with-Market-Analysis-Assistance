"""Bounded in-memory validation and chat session storage."""

import copy
import threading
import time
import uuid

_SESSION_TTL_SECONDS = 2 * 60 * 60
_MAX_SESSIONS = 200
_MAX_TURNS = 12
_CHAT_WINDOW_SECONDS = 60
_MAX_CHAT_REQUESTS_PER_WINDOW = 6

_lock = threading.RLock()
_sessions: dict[str, dict] = {}


def _prune(now: float) -> None:
    expired = [
        session_id
        for session_id, session in _sessions.items()
        if now - session["updatedAt"] > _SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        del _sessions[session_id]

    if len(_sessions) > _MAX_SESSIONS:
        oldest = sorted(_sessions, key=lambda key: _sessions[key]["updatedAt"])
        for session_id in oldest[: len(_sessions) - _MAX_SESSIONS]:
            del _sessions[session_id]


def create_session(context: dict) -> str:
    now = time.time()
    session_id = str(uuid.uuid4())
    with _lock:
        _prune(now)
        _sessions[session_id] = {
            "context": copy.deepcopy(context),
            "history": [],
            "chatRequestTimes": [],
            "createdAt": now,
            "updatedAt": now,
        }
    return session_id


def get_session(session_id: str) -> dict | None:
    now = time.time()
    with _lock:
        _prune(now)
        session = _sessions.get(session_id)
        if session is None:
            return None
        session["updatedAt"] = now
        return copy.deepcopy(session)


def append_turn(session_id: str, message: str, reply: str) -> bool:
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return False
        session["history"].append({"message": message, "reply": reply})
        session["history"] = session["history"][-_MAX_TURNS:]
        session["updatedAt"] = time.time()
        return True


def reserve_chat_request(session_id: str) -> None:
    now = time.time()
    with _lock:
        _prune(now)
        session = _sessions.get(session_id)
        if session is None:
            raise KeyError("Session not found or expired.")

        cutoff = now - _CHAT_WINDOW_SECONDS
        recent = [
            timestamp
            for timestamp in session["chatRequestTimes"]
            if timestamp >= cutoff
        ]
        if len(recent) >= _MAX_CHAT_REQUESTS_PER_WINDOW:
            raise RuntimeError("Chat rate limit exceeded.")

        recent.append(now)
        session["chatRequestTimes"] = recent
        session["updatedAt"] = now


def clear_sessions() -> None:
    with _lock:
        _sessions.clear()
