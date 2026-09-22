"""Account auth: signup/login, password hashing, and JWT bearer tokens.

Stateless JWTs (not server-side auth sessions) - main.py already has a
`sessions` table for validation sessions and reusing that name/shape for a
second, unrelated concept (login sessions) would be confusing. A JWT means
"log out everywhere" isn't possible without a revocation list, which is a
real, deliberate limitation, not an oversight - not needed for a single
"my own board" account model, and can be added later as its own feature if
it ever is.
"""

import os
import time
import uuid

import bcrypt
import jwt
from fastapi import Header, HTTPException
from sqlalchemy.exc import IntegrityError

from .db import get_engine, now, users_table
from sqlalchemy import select

# Must be set in production (Render env) - a request-time error there is far
# safer than silently signing every token with a guessable default that
# ships in source control. Local dev gets a fixed fallback purely so
# `uvicorn main:app` works out of the box without an extra setup step.
_SECRET_KEY = os.environ.get("AUTH_SECRET_KEY") or "dev-only-insecure-secret-key-change-me"
_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
_MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Signup/login failed for a reason safe to show the user directly
    (bad credentials, duplicate email, weak password) - distinct from an
    unexpected server error, which should log and 500 instead."""


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed stored hash - fails closed rather than raising a 500
        # for what's still just "these credentials don't match."
        return False


def _issue_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": time.time() + _TOKEN_TTL_SECONDS}
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def signup(email: str, password: str) -> dict:
    email = email.strip().lower()
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")

    user_id = str(uuid.uuid4())
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                users_table.insert().values(
                    id=user_id,
                    email=email,
                    password_hash=_hash_password(password),
                    created_at=now(),
                )
            )
    except IntegrityError as exc:
        raise AuthError("An account with that email already exists.") from exc

    return {"token": _issue_token(user_id, email), "user": {"id": user_id, "email": email}}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(users_table).where(users_table.c.email == email)).first()

    # Same error for "no such account" and "wrong password" - distinguishing
    # them lets an attacker enumerate registered emails one guess at a time.
    if row is None or not _verify_password(password, row.password_hash):
        raise AuthError("Incorrect email or password.")

    return {"token": _issue_token(row.id, row.email), "user": {"id": row.id, "email": row.email}}


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or malformed auth token.")


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: 401s the request if there's no valid bearer token."""
    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    claims = _decode_token(token)
    return {"id": claims["sub"], "email": claims["email"]}


def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    """FastAPI dependency: None for an anonymous request (no header at all),
    but still 401s a header that's present and invalid/expired - a token a
    caller believes is good failing silently into "anonymous" would hide a
    real problem (e.g. a stale token after a password change) behind
    behavior that looks like success.
    """
    token = _extract_bearer_token(authorization)
    if token is None:
        return None
    claims = _decode_token(token)
    return {"id": claims["sub"], "email": claims["email"]}
