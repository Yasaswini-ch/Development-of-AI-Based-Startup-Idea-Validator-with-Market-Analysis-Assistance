"""
Federated Google SSO (OAuth 2.0) - Platform Layer (AFFINITY 5-pillar spec
§4.6). Verifies the Google ID token the frontend's Google Sign-In button
hands back, so the server never has to trust a client-asserted email - the
same reasoning agent/auth.py's own password verification exists for, just
against Google's signature instead of a stored hash.

Kept in its own module (not folded into auth.py) so the one function that
needs network access to fetch Google's public signing keys (via the
`google-auth` library) is a single, easily-mocked seam - every test that
exercises the Google login flow patches `verify_google_id_token` instead
of needing a live network call or a real Google account.
"""

import os

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


class GoogleAuthError(Exception):
    """The ID token failed verification (expired, wrong audience, bad
    signature) or GOOGLE_OAUTH_CLIENT_ID isn't configured - safe to show
    the user directly, same split AuthError already draws in auth.py.
    """


_request = google_requests.Request()


def verify_google_id_token(id_token_str: str) -> dict:
    """Verify `id_token_str` against Google's own public keys and the
    configured OAuth client ID, and return {"sub", "email", "name",
    "picture"} straight from the verified token's claims - never from
    anything the client sent outside the signed token itself.
    """
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    if not client_id:
        raise GoogleAuthError("Google sign-in is not configured on this server.")

    if not id_token_str or not isinstance(id_token_str, str):
        raise GoogleAuthError("Missing Google ID token.")

    try:
        claims = google_id_token.verify_oauth2_token(id_token_str, _request, audience=client_id)
    except ValueError as exc:
        # verify_oauth2_token raises plain ValueError for every failure
        # mode (expired, wrong audience, malformed, bad signature) - none
        # of those messages are safe to show verbatim (they can echo back
        # attacker-controlled token contents), so they're logged-worthy
        # but not user-facing.
        raise GoogleAuthError("Google sign-in could not be verified. Please try again.") from exc

    email = claims.get("email")
    if not email:
        raise GoogleAuthError("Google did not share an email address for this account.")
    # Google sets this False for an unverified email address on the Google
    # account itself (rare, but possible) - treated the same as "no email"
    # since an unverified email is not a trustworthy account identifier.
    if claims.get("email_verified") is False:
        raise GoogleAuthError("This Google account's email address is not verified.")

    return {
        "sub": claims["sub"],
        "email": email.strip().lower(),
        "name": claims.get("name"),
        "picture": claims.get("picture"),
    }


__all__ = ["GoogleAuthError", "verify_google_id_token"]
