"""Contract tests for claiming an anonymous validation session onto an
account signed into right after (agent/session_store.claim_session,
POST /me/claim-session) - see App.jsx's handleAuthenticated, which fires
this the moment a guest run's sign-in succeeds so it shows up in
GET /me/history instead of staying stuck in device-local history.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete

import main
from agent.auth import signup
from agent.db import get_engine, sessions_table, users_table
from agent.session_store import claim_session, create_session, list_sessions_for_user


def _clear_tables():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(sessions_table))
        conn.execute(delete(users_table))


class ClaimSessionModuleTests(unittest.TestCase):
    def setUp(self):
        _clear_tables()

    def test_claims_an_ownerless_session(self):
        session_id = create_session({"idea": "A plant swap app"})
        claimed = claim_session(session_id, "user-1")
        self.assertTrue(claimed)
        entries = list_sessions_for_user("user-1")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sessionId"], session_id)

    def test_claiming_again_by_the_same_user_is_a_no_op_success(self):
        session_id = create_session({"idea": "A plant swap app"})
        claim_session(session_id, "user-1")
        claimed_again = claim_session(session_id, "user-1")
        self.assertTrue(claimed_again)

    def test_does_not_reassign_a_session_already_owned_by_someone_else(self):
        session_id = create_session({"idea": "A plant swap app"}, user_id="user-1")
        claimed = claim_session(session_id, "user-2")
        self.assertFalse(claimed)
        self.assertEqual(list_sessions_for_user("user-2"), [])
        self.assertEqual(len(list_sessions_for_user("user-1")), 1)

    def test_unknown_session_id_returns_false(self):
        self.assertFalse(claim_session("does-not-exist", "user-1"))


class ClaimSessionRouteTests(unittest.TestCase):
    """POST /me/claim-session end to end through main.py."""

    def setUp(self):
        _clear_tables()
        self.client = TestClient(main.app)

    def _signed_up_headers(self, email="founder@example.com"):
        result = signup(email, "correct-horse-battery")
        return {"Authorization": f"Bearer {result['token']}"}

    def test_claims_a_guest_session_onto_the_new_account(self):
        session_id = create_session({"idea": "A plant swap app"})
        headers = self._signed_up_headers()

        response = self.client.post("/me/claim-session", json={"sessionId": session_id}, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["claimed"])
        history = self.client.get("/me/history", headers=headers)
        self.assertEqual(len(history.json()["entries"]), 1)

    def test_unknown_session_id_is_a_404(self):
        headers = self._signed_up_headers()
        response = self.client.post("/me/claim-session", json={"sessionId": "does-not-exist"}, headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_requires_auth(self):
        session_id = create_session({"idea": "A plant swap app"})
        response = self.client.post("/me/claim-session", json={"sessionId": session_id})
        self.assertEqual(response.status_code, 401)

    def test_session_already_owned_by_another_account_is_a_404(self):
        other_session_id = create_session({"idea": "A plant swap app"}, user_id="some-other-user")
        headers = self._signed_up_headers()
        response = self.client.post("/me/claim-session", json={"sessionId": other_session_id}, headers=headers)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
