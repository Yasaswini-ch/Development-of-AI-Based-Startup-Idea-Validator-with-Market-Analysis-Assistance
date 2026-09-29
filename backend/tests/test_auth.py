"""Tests for agent/auth.py and its HTTP endpoints (main.py) - user accounts
had zero test coverage before this file, discovered while auditing what
Track F (testing/hardening) still had open.

Covers: signup/login success and failure paths, token verification
(/auth/me), the require_user vs optional_user distinction /validate relies
on to tag a session with user_id only when actually signed in, and
GET /me/history end to end (signup -> validate -> history lists it).
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import job_store, session_store
from agent.auth import AuthError, is_admin, login, signup
from agent.db import get_engine, users_table
import bcrypt
from sqlalchemy import delete, select


def _clear_users():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(users_table))


class AuthModuleTests(unittest.TestCase):
    """agent/auth.py directly - no HTTP layer."""

    def setUp(self):
        _clear_users()

    def test_signup_returns_a_token_and_the_new_user(self):
        result = signup("Founder@Example.com", "correct-horse-battery")
        self.assertTrue(result["token"])
        self.assertEqual(result["user"]["email"], "founder@example.com")  # normalized lowercase

    def test_signup_rejects_a_short_password(self):
        with self.assertRaises(AuthError):
            signup("founder@example.com", "short")

    def test_signup_rejects_a_duplicate_email(self):
        signup("founder@example.com", "correct-horse-battery")
        with self.assertRaises(AuthError):
            signup("founder@example.com", "another-password")

    def test_signup_email_is_case_and_whitespace_normalized_for_dedupe(self):
        signup("founder@example.com", "correct-horse-battery")
        with self.assertRaises(AuthError):
            signup("  Founder@EXAMPLE.com  ", "another-password")

    def test_login_succeeds_with_correct_credentials(self):
        signup("founder@example.com", "correct-horse-battery")
        result = login("founder@example.com", "correct-horse-battery")
        self.assertTrue(result["token"])
        self.assertEqual(result["user"]["email"], "founder@example.com")

    def test_new_hashes_use_the_configured_bcrypt_cost(self):
        signup("founder@example.com", "correct-horse-battery")
        with get_engine().connect() as conn:
            stored = conn.execute(select(users_table.c.password_hash)).scalar_one()
        self.assertTrue(stored.startswith("$2b$10$"))

    def test_login_upgrades_an_older_higher_cost_hash(self):
        signup("founder@example.com", "correct-horse-battery")
        old_hash = bcrypt.hashpw(b"correct-horse-battery", bcrypt.gensalt(rounds=12)).decode()
        with get_engine().begin() as conn:
            conn.execute(users_table.update().values(password_hash=old_hash))

        login("founder@example.com", "correct-horse-battery")

        with get_engine().connect() as conn:
            stored = conn.execute(select(users_table.c.password_hash)).scalar_one()
        self.assertTrue(stored.startswith("$2b$10$"))
        self.assertTrue(login("founder@example.com", "correct-horse-battery")["token"])

    def test_login_fails_with_wrong_password(self):
        signup("founder@example.com", "correct-horse-battery")
        with self.assertRaises(AuthError):
            login("founder@example.com", "wrong-password")

    def test_login_fails_for_an_account_that_does_not_exist(self):
        with self.assertRaises(AuthError):
            login("nobody@example.com", "whatever-password")


class IsAdminSelfHealTests(unittest.TestCase):
    """is_admin() self-promotes an ADMIN_EMAILS match on every lookup, not
    just once at process startup (db.py's _bootstrap_admin_emails) - a host
    with no persistent disk (e.g. Render's free tier, plain SQLite) resets
    the database on every deploy, so an account created after the deploy
    that set ADMIN_EMAILS would otherwise never get promoted until another
    restart.
    """

    def setUp(self):
        _clear_users()
        os.environ.pop("ADMIN_EMAILS", None)

    def tearDown(self):
        os.environ.pop("ADMIN_EMAILS", None)

    def test_promotes_a_matching_account_on_first_lookup(self):
        result = signup("founder@example.com", "correct-horse-battery")
        with patch.dict(os.environ, {"ADMIN_EMAILS": "founder@example.com"}):
            self.assertTrue(is_admin(result["user"]["id"]))
        # The promotion itself is persisted, not just returned for this call.
        self.assertTrue(is_admin(result["user"]["id"]))

    def test_matches_case_insensitively_and_ignores_whitespace(self):
        result = signup("founder@example.com", "correct-horse-battery")
        with patch.dict(os.environ, {"ADMIN_EMAILS": " Founder@Example.com , someone-else@example.com "}):
            self.assertTrue(is_admin(result["user"]["id"]))

    def test_does_not_promote_a_non_matching_account(self):
        result = signup("founder@example.com", "correct-horse-battery")
        with patch.dict(os.environ, {"ADMIN_EMAILS": "someone-else@example.com"}):
            self.assertFalse(is_admin(result["user"]["id"]))

    def test_returns_false_for_an_unknown_user_id(self):
        with patch.dict(os.environ, {"ADMIN_EMAILS": "founder@example.com"}):
            self.assertFalse(is_admin("not-a-real-user-id"))


class AuthEndpointTests(unittest.TestCase):
    def setUp(self):
        _clear_users()
        main._clear_rate_limits()
        self.client = TestClient(main.app)

    def test_signup_endpoint_returns_200_with_token(self):
        response = self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "correct-horse-battery"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])

    def test_signup_endpoint_rejects_an_invalid_email(self):
        response = self.client.post("/auth/signup", json={"email": "not-an-email", "password": "correct-horse-battery"})
        self.assertEqual(response.status_code, 422)

    def test_signup_endpoint_returns_400_for_a_duplicate_email(self):
        self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "correct-horse-battery"})
        response = self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "another-password"})
        self.assertEqual(response.status_code, 400)

    def test_login_endpoint_returns_401_for_wrong_password(self):
        self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "correct-horse-battery"})
        response = self.client.post("/auth/login", json={"email": "founder@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 401)
        # Same error shape as "account doesn't exist" - not confirming which part was wrong.
        self.assertIn("Incorrect email or password", response.json()["error"])

    def test_auth_me_requires_a_bearer_token(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_auth_me_rejects_a_malformed_token(self):
        response = self.client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
        self.assertEqual(response.status_code, 401)

    def test_auth_me_returns_the_signed_in_user_with_a_valid_token(self):
        signup_response = self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "correct-horse-battery"})
        token = signup_response.json()["token"]
        response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "founder@example.com")

    def test_auth_rate_limit_kicks_in_after_repeated_attempts(self):
        for _ in range(20):
            response = self.client.post("/auth/login", json={"email": "nobody@example.com", "password": "x"})
        self.assertEqual(response.status_code, 429)


class OptionalUserValidateFlowTests(unittest.TestCase):
    """/validate must work identically whether or not the caller is signed
    in - optional_user() should never turn a normal anonymous request into
    a 401, only tag the resulting session with user_id when a valid token
    IS present.
    """

    def setUp(self):
        _clear_users()
        main._clear_cache()
        main._clear_rate_limits()
        job_store.clear_jobs()
        session_store.clear_sessions()
        self.client = TestClient(main.app)

    @patch("main.pipeline.invoke")
    def test_anonymous_validate_request_still_succeeds(self, invoke):
        invoke.return_value = {"summary": "S", "results": [], "errors": {}}
        response = self.client.post("/validate", json={"idea": "Anonymous idea"})
        self.assertEqual(response.status_code, 200)

    @patch("main.pipeline.invoke")
    def test_validate_with_an_invalid_bearer_token_is_rejected_not_silently_anonymous(self, invoke):
        invoke.return_value = {"summary": "S", "results": [], "errors": {}}
        response = self.client.post(
            "/validate",
            json={"idea": "Idea"},
            headers={"Authorization": "Bearer garbage-token"},
        )
        self.assertEqual(response.status_code, 401)

    @patch("main.pipeline.invoke")
    def test_signed_in_validation_shows_up_in_me_history(self, invoke):
        invoke.return_value = {"summary": "S", "results": [], "errors": {}}
        signup_response = self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "correct-horse-battery"})
        token = signup_response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        self.client.post("/validate", json={"idea": "My tracked idea"}, headers=headers)

        history = self.client.get("/me/history", headers=headers)
        self.assertEqual(history.status_code, 200)
        ideas = [entry["idea"] for entry in history.json()["entries"]]
        self.assertIn("My tracked idea", ideas)

    @patch("main.pipeline.invoke")
    def test_anonymous_validation_does_not_show_up_in_anyones_history(self, invoke):
        invoke.return_value = {"summary": "S", "results": [], "errors": {}}
        signup_response = self.client.post("/auth/signup", json={"email": "founder@example.com", "password": "correct-horse-battery"})
        token = signup_response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        self.client.post("/validate", json={"idea": "Anonymous idea, not signed in"})

        history = self.client.get("/me/history", headers=headers)
        ideas = [entry["idea"] for entry in history.json()["entries"]]
        self.assertNotIn("Anonymous idea, not signed in", ideas)

    def test_me_history_requires_sign_in(self):
        response = self.client.get("/me/history")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
