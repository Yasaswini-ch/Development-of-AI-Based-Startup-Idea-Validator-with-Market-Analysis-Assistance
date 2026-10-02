"""Password reset: single-use, short-lived tokens, and an endpoint that never
reveals which emails have accounts."""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

import main
from agent.auth import AuthError, login, request_password_reset, reset_password, signup
from agent.db import get_engine, password_resets_table, users_table

OLD = "correct-horse-battery"
NEW = "a-brand-new-passphrase"


def _clear():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(password_resets_table))
        conn.execute(delete(users_table))


class ResetModuleTests(unittest.TestCase):
    def setUp(self):
        _clear()
        signup("founder@example.com", OLD)

    def test_a_valid_token_sets_the_new_password_and_is_single_use(self):
        email, token = request_password_reset("Founder@Example.com")
        self.assertEqual(email, "founder@example.com")
        reset_password(token, NEW)
        self.assertTrue(login("founder@example.com", NEW)["token"])
        with self.assertRaises(AuthError):
            login("founder@example.com", OLD)
        with self.assertRaises(AuthError):
            reset_password(token, "yet-another-passphrase")  # already used

    def test_unknown_email_returns_none(self):
        self.assertIsNone(request_password_reset("nobody@example.com"))
        self.assertIsNone(request_password_reset(""))

    def test_only_a_hash_of_the_token_is_stored(self):
        _, token = request_password_reset("founder@example.com")
        with get_engine().begin() as conn:
            hashes = [r.token_hash for r in conn.execute(select(password_resets_table)).all()]
        self.assertEqual(len(hashes), 1)
        self.assertNotIn(token, hashes)

    def test_a_new_request_replaces_the_previous_link(self):
        _, first = request_password_reset("founder@example.com")
        _, second = request_password_reset("founder@example.com")
        with self.assertRaises(AuthError):
            reset_password(first, NEW)
        reset_password(second, NEW)

    def test_an_expired_token_is_rejected(self):
        _, token = request_password_reset("founder@example.com")
        with get_engine().begin() as conn:
            conn.execute(password_resets_table.update().values(expires_at=time.time() - 1))
        with self.assertRaises(AuthError):
            reset_password(token, NEW)
        self.assertTrue(login("founder@example.com", OLD)["token"])  # password unchanged

    def test_a_garbage_token_and_a_short_password_are_rejected(self):
        with self.assertRaises(AuthError):
            reset_password("not-a-real-token-at-all-0000", NEW)
        _, token = request_password_reset("founder@example.com")
        with self.assertRaises(AuthError):
            reset_password(token, "short")
        reset_password(token, NEW)  # the short attempt did not burn the token


class ResetEndpointTests(unittest.TestCase):
    def setUp(self):
        _clear()
        signup("founder@example.com", OLD)
        main._rate_limit_hits.clear() if hasattr(main, "_rate_limit_hits") else None
        self.client = TestClient(main.app)

    def test_known_and_unknown_emails_get_the_same_answer(self):
        with patch("main.send_password_reset_email", return_value=True) as sent:
            known = self.client.post("/auth/forgot-password", json={"email": "founder@example.com"})
            unknown = self.client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
        self.assertEqual(known.status_code, 202)
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(sent.call_count, 1)  # only the real account was emailed
        self.assertEqual(sent.call_args.args[0], "founder@example.com")
        self.assertIn("?reset=", sent.call_args.args[1])

    def test_a_malformed_email_gets_the_same_answer_and_sends_nothing(self):
        with patch("main.send_password_reset_email") as sent:
            res = self.client.post("/auth/forgot-password", json={"email": "not-an-email"})
        self.assertEqual(res.status_code, 202)
        sent.assert_not_called()

    def test_full_flow_through_the_http_endpoints(self):
        with patch("main.send_password_reset_email", return_value=True) as sent:
            self.client.post("/auth/forgot-password", json={"email": "founder@example.com"})
        token = sent.call_args.args[1].split("?reset=")[1]

        bad = self.client.post("/auth/reset-password", json={"token": "x" * 30, "password": NEW})
        self.assertEqual(bad.status_code, 400)

        ok = self.client.post("/auth/reset-password", json={"token": token, "password": NEW})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.post("/auth/login", json={"email": "founder@example.com", "password": NEW}).status_code, 200)

        again = self.client.post("/auth/reset-password", json={"token": token, "password": "another-passphrase"})
        self.assertEqual(again.status_code, 400)


if __name__ == "__main__":
    unittest.main()
