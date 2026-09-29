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
from .google_auth import verify_google_id_token
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


# bcrypt cost 10 is the OWASP minimum work factor. Cost 12 (bcrypt's default)
# took several seconds per sign-in on Render's free 0.1-CPU instance; stored
# hashes at a different cost are upgraded on the next successful login.
_BCRYPT_ROUNDS = 10


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def _hash_cost(password_hash: str) -> int | None:
    try:
        return int(password_hash.split("$")[2])
    except (IndexError, ValueError):
        return None


def _verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        # A Google-only account (see login_with_google) never set a
        # password - fails closed the same as a wrong password, not a
        # crash, so a passwordless account can't be logged into here at
        # all rather than raising on the None.encode() below.
        return False
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


def _row_to_user(row) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "authProvider": row.auth_provider,
        "avatarUrl": row.avatar_url,
    }


def login_with_google(id_token_str: str) -> dict:
    """Verify the Google ID token (agent/google_auth.py) and sign the
    caller in, creating a new passwordless account on first sign-in.

    Looked up by email, same as the local login() above - a Google
    account with the same (Google-verified) email as an existing local
    account is treated as that same account rather than a second, linked
    identity: simpler than real account linking, and safe here because
    Google's own email_verified claim is the trust anchor either way.
    """
    claims = verify_google_id_token(id_token_str)
    email = claims["email"]

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(users_table).where(users_table.c.email == email)).first()

        if row is None:
            user_id = str(uuid.uuid4())
            conn.execute(
                users_table.insert().values(
                    id=user_id,
                    email=email,
                    password_hash=None,
                    created_at=now(),
                    auth_provider="google",
                    avatar_url=claims.get("picture"),
                )
            )
            row = conn.execute(select(users_table).where(users_table.c.id == user_id)).first()
        elif row.auth_provider != "google" or row.avatar_url != claims.get("picture"):
            # Keep an existing account's provider/avatar in sync with
            # Google's own record on every sign-in - a local account that
            # later signs in with Google picks up "google" once it has
            # actually verified that email through Google, and an avatar
            # Google has since changed follows along too.
            conn.execute(
                users_table.update()
                .where(users_table.c.id == row.id)
                .values(auth_provider="google", avatar_url=claims.get("picture"))
            )
            row = conn.execute(select(users_table).where(users_table.c.id == row.id)).first()

    return {"token": _issue_token(row.id, row.email), "user": _row_to_user(row)}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(users_table).where(users_table.c.email == email)).first()

    # Same error for "no such account" and "wrong password" - distinguishing
    # them lets an attacker enumerate registered emails one guess at a time.
    if row is None or not _verify_password(password, row.password_hash):
        raise AuthError("Incorrect email or password.")

    if _hash_cost(row.password_hash) != _BCRYPT_ROUNDS:
        with engine.begin() as conn:
            conn.execute(
                users_table.update().where(users_table.c.id == row.id).values(password_hash=_hash_password(password))
            )

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


def _admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def is_admin(user_id: str) -> bool:
    """Looked up fresh from the users table rather than carried in the JWT
    payload - there's no self-service way to become an admin (see db.py's
    is_admin column comment), so this is already a rare, low-traffic path,
    and a fresh lookup means revoking admin access takes effect
    immediately instead of waiting out whatever is left of that user's
    up-to-30-day token.

    Also self-heals against ADMIN_EMAILS here, not just once at startup
    (db.py's _bootstrap_admin_emails) - on a host with no persistent disk
    (e.g. Render's free tier, plain SQLite), the deploy that applies a new
    ADMIN_EMAILS value also resets the on-disk database, so the one-time
    startup bootstrap can run before the matching account exists in that
    fresh database and never get another chance. Checking here instead
    covers that account the next time it's looked up at all - no redeploy
    ordering required - at the cost of one extra cheap lookup on accounts
    that are already flagged (skipped) or already admin (returns early
    below without ever calling this).
    """
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(users_table.c.is_admin, users_table.c.email).where(users_table.c.id == user_id)
        ).first()
    if row is None:
        return False
    if row.is_admin:
        return True
    if row.email.lower() not in _admin_emails():
        return False

    with engine.begin() as conn:
        conn.execute(users_table.update().where(users_table.c.id == user_id).values(is_admin=True))
    return True


def account_profile(user_id: str) -> dict:
    """{"authProvider", "avatarUrl"} for GET /auth/me, read fresh from the
    users table (neither is in the JWT). An unknown id - e.g. a token for an
    account wiped by a SQLite reset - gets the local/no-avatar defaults
    rather than an error, since require_user already accepted the token.
    """
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(users_table.c.auth_provider, users_table.c.avatar_url).where(users_table.c.id == user_id)
        ).first()
    if row is None:
        return {"authProvider": "local", "avatarUrl": None}
    return {"authProvider": row.auth_provider or "local", "avatarUrl": row.avatar_url}


def require_admin(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency for GET /admin/platform-metrics: 401s like
    require_user for no/invalid token, 403s for a valid token belonging to
    a non-admin account.
    """
    user = require_user(authorization)
    if not is_admin(user["id"]):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
