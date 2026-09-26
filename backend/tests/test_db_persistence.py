"""Tests for agent/db.py's handling of the SQLite fallback - the case where
DATABASE_URL is missing on a deployed host and every user, validation and
admin flag would be wiped on the next redeploy.
"""

import os
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from agent.db import database_backend, get_engine, reset_engine

_ENV_KEYS = ("DATABASE_URL", "REQUIRE_PERSISTENT_DB", "RENDER")


class DatabasePersistenceTests(unittest.TestCase):
    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in _ENV_KEYS}
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        reset_engine()

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_engine()

    def test_backend_names_never_include_the_url(self):
        self.assertEqual(database_backend("sqlite:///./affinity.db"), "sqlite")
        self.assertEqual(database_backend("postgresql+psycopg://u:secret@host:5432/db"), "postgresql")

    def test_unset_and_blank_database_url_fall_back_to_sqlite(self):
        self.assertEqual(database_backend(), "sqlite")
        os.environ["DATABASE_URL"] = "   "
        self.assertEqual(database_backend(), "sqlite")

    def test_render_style_postgres_url_is_recognised(self):
        os.environ["DATABASE_URL"] = "postgres://u:secret@host:5432/db"
        self.assertEqual(database_backend(), "postgresql")

    def test_require_persistent_db_refuses_the_sqlite_fallback(self):
        os.environ["REQUIRE_PERSISTENT_DB"] = "1"
        with self.assertRaises(RuntimeError):
            get_engine()

    def test_sqlite_fallback_on_render_logs_a_warning(self):
        os.environ["RENDER"] = "true"
        with self.assertLogs("agent.db", level="WARNING") as logs:
            get_engine()
        self.assertIn("NOT persistent", logs.output[0])

    def test_health_reports_the_database_backend(self):
        from main import app

        response = TestClient(app).get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "sqlite")


if __name__ == "__main__":
    unittest.main()
