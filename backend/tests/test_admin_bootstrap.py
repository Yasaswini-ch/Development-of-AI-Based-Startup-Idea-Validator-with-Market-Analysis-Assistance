"""Tests for agent/db.py's ADMIN_EMAILS bootstrap - the only way to promote
an account to admin on a host with no interactive shell or SQL console
(e.g. Render's free tier), where a direct `UPDATE users SET is_admin ...`
isn't reachable.
"""

import os
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, select

from agent.auth import signup
from agent.db import get_engine, reset_engine, users_table


def _is_admin(email):
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(users_table.c.is_admin).where(users_table.c.email == email)).first()
    return bool(row and row.is_admin)


class AdminBootstrapTests(unittest.TestCase):
    def setUp(self):
        get_engine()  # ensure the table exists before clearing it
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(delete(users_table))
        os.environ.pop("ADMIN_EMAILS", None)
        reset_engine()

    def tearDown(self):
        os.environ.pop("ADMIN_EMAILS", None)
        reset_engine()

    def test_promotes_a_matching_existing_user_on_next_engine_creation(self):
        signup("founder@example.com", "hunter22")
        self.assertFalse(_is_admin("founder@example.com"))

        os.environ["ADMIN_EMAILS"] = "founder@example.com"
        reset_engine()
        get_engine()

        self.assertTrue(_is_admin("founder@example.com"))

    def test_matches_case_insensitively_and_ignores_whitespace(self):
        signup("founder@example.com", "hunter22")

        os.environ["ADMIN_EMAILS"] = " Founder@Example.com , someone-else@example.com "
        reset_engine()
        get_engine()

        self.assertTrue(_is_admin("founder@example.com"))

    def test_does_nothing_when_the_env_var_is_unset(self):
        signup("founder@example.com", "hunter22")
        reset_engine()
        get_engine()
        self.assertFalse(_is_admin("founder@example.com"))

    def test_does_nothing_when_no_user_matches(self):
        signup("founder@example.com", "hunter22")
        os.environ["ADMIN_EMAILS"] = "nobody@example.com"
        reset_engine()
        get_engine()
        self.assertFalse(_is_admin("founder@example.com"))


if __name__ == "__main__":
    unittest.main()
