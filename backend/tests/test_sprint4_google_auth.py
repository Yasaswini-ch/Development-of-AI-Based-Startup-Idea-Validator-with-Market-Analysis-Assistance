"""Contract tests for Sprint 4 of the 5-pillar spec: Platform Layer -
Federated Google SSO (agent/google_auth.py, agent/auth.login_with_google,
POST /auth/google).

Every test mocks agent.auth.verify_google_id_token instead of calling
Google's real network-backed verifier (agent/google_auth.py's whole
purpose is to be that one mockable seam) - no test here makes a network
call or needs a real Google account/client ID.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete

import main
from agent.auth import login, login_with_google, signup
from agent.db import get_engine, users_table
from agent.google_auth import GoogleAuthError, verify_google_id_token


def _clear_users():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(users_table))


_CLAIMS = {"sub": "google-sub-123", "email": "founder@example.com", "name": "Founder", "picture": "https://example.com/pic.jpg"}


class GoogleAuthModuleTests(unittest.TestCase):
    def setUp(self):
        _clear_users()

    def test_missing_client_id_env_var_raises(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_OAUTH_CLIENT_ID", None)
            with self.assertRaises(GoogleAuthError):
                verify_google_id_token("some-token")

    def test_invalid_token_raises_a_safe_message_not_the_raw_error(self):
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "test-client-id"}):
            with self.assertRaises(GoogleAuthError):
                verify_google_id_token("not-a-real-jwt")

    @patch("agent.auth.verify_google_id_token", return_value=_CLAIMS)
    def test_first_sign_in_creates_a_passwordless_account(self, _mock):
        result = login_with_google("fake-id-token")
        self.assertTrue(result["token"])
        self.assertEqual(result["user"]["email"], "founder@example.com")
        self.assertEqual(result["user"]["authProvider"], "google")
        self.assertEqual(result["user"]["avatarUrl"], "https://example.com/pic.jpg")

    @patch("agent.auth.verify_google_id_token", return_value=_CLAIMS)
    def test_second_sign_in_reuses_the_same_account(self, _mock):
        first = login_with_google("fake-id-token")
        second = login_with_google("fake-id-token")
        self.assertEqual(first["user"]["id"], second["user"]["id"])

    @patch("agent.auth.verify_google_id_token", return_value=_CLAIMS)
    def test_existing_local_account_with_the_same_email_is_reused_not_duplicated(self, _mock):
        local = signup("founder@example.com", "correct-horse-battery")
        google = login_with_google("fake-id-token")
        self.assertEqual(local["user"]["id"], google["user"]["id"])
        self.assertEqual(google["user"]["authProvider"], "google")

    @patch("agent.auth.verify_google_id_token", return_value=_CLAIMS)
    def test_local_password_login_still_works_after_linking_via_google(self, _mock):
        signup("founder@example.com", "correct-horse-battery")
        login_with_google("fake-id-token")
        result = login("founder@example.com", "correct-horse-battery")
        self.assertTrue(result["token"])

    def test_google_only_account_cannot_be_password_logged_in(self):
        with patch("agent.auth.verify_google_id_token", return_value=_CLAIMS):
            login_with_google("fake-id-token")
        with self.assertRaises(Exception):
            login("founder@example.com", "whatever-password")


class GoogleAuthRouteTests(unittest.TestCase):
    """POST /auth/google end to end through main.py."""

    def setUp(self):
        _clear_users()
        self.client = TestClient(main.app)

    @patch("main.auth_login_with_google")
    def test_valid_token_returns_200_with_a_token(self, mock_login):
        mock_login.return_value = {"token": "jwt-token", "user": {"id": "u1", "email": "a@b.com", "authProvider": "google", "avatarUrl": None}}
        response = self.client.post("/auth/google", json={"idToken": "fake"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "jwt-token")

    @patch("main.auth_login_with_google", side_effect=GoogleAuthError("Google sign-in could not be verified. Please try again."))
    def test_invalid_token_returns_401_with_a_safe_message(self, _mock):
        response = self.client.post("/auth/google", json={"idToken": "bad-token"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_missing_id_token_field_is_a_422(self):
        response = self.client.post("/auth/google", json={})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
