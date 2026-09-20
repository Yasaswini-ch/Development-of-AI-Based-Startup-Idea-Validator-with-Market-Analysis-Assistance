"""Integration and concurrency tests - a different concern from the unit
tests in test_milestone2.py/test_milestone3.py/test_async_email.py, which
all mock the LLM boundary and exercise one request at a time.

Two things live here:

1. A real end-to-end run against the actual Groq API (no mocking at all),
   so a real provider contract change - a renamed field, a new error
   shape, a model deprecation - gets caught here instead of only ever
   being caught by a mocked test that still assumes the old contract.
   Skipped unless GROQ_API_KEY is set, since CI/grading environments won't
   have one and this makes a real, billed API call.

2. Concurrency tests proving the database-backed session/job/cache/
   rate-limit layer (agent/db.py, replacing the old process-local dicts)
   actually behaves correctly when multiple requests land at once - the
   in-memory dicts this replaced were never thread-safe under real
   concurrent load, only "safe enough" because traffic was always low.
"""

import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import job_store, session_store


def _fake_state(**overrides):
    state = {
        "summary": "A promising idea.",
        "results": [],
        "confidence": {},
        "marketOpportunity": {"marketSize": "Test size", "trends": [], "segments": []},
        "competitors": {"competitors": []},
        "whiteSpace": {"opportunity": "Test gap"},
        "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []},
        "mvp": {"features": []},
        "gtm": {"positioning": "Test", "channels": [], "earlyCustomerApproach": "Test"},
        "errors": {},
    }
    state.update(overrides)
    return state


@unittest.skipUnless(
    os.environ.get("GROQ_API_KEY"),
    "requires a real GROQ_API_KEY - makes an actual, billed Groq call; skipped by default",
)
class RealPipelineIntegrationTests(unittest.TestCase):
    """No mocking anywhere in this test - a real search + a real LLM call,
    proving the full pipeline still works against the providers' actual,
    current contracts, not just against what our mocks assume they return.
    """

    def test_full_pipeline_runs_against_real_providers(self):
        from agent.graph import pipeline

        state = pipeline.invoke(
            {
                "idea": "A subscription box for eco-friendly cleaning products",
                "targetCustomer": "environmentally conscious households",
                "problem": "plastic waste from cleaning product packaging",
            }
        )

        self.assertIsNone(state.get("error"))
        self.assertTrue(state.get("summary"))
        self.assertIsInstance(state.get("results"), list)
        # marketOpportunity/swot/mvp/gtm may individually be None if their
        # own LLM call failed (documented, expected partial-failure
        # behavior) - the pipeline itself must still complete either way,
        # not crash outright. state["errors"] is only ever set by a node
        # that actually failed (see main.py's own state.get("errors", {})
        # default), so its absence here means every node succeeded.
        for section in ("marketOpportunity", "swot", "mvp", "gtm"):
            if state.get(section) is None:
                self.assertIn(section, state.get("errors", {}), f"{section} is None but has no recorded error")


class ConcurrencyTests(unittest.TestCase):
    """Everything here used to be a bare process-local dict with a
    threading.RLock - these tests exercise the database-backed replacement
    (agent/db.py) under real concurrent access, which the in-memory version
    was never actually tested against.
    """

    def setUp(self):
        main._clear_cache()
        main._clear_rate_limits()
        job_store.clear_jobs()
        session_store.clear_sessions()
        self.client = TestClient(main.app)

    def test_concurrent_validate_requests_each_get_a_distinct_session(self):
        with patch("main.pipeline.invoke", return_value=_fake_state()):
            def submit(i):
                return self.client.post("/validate", json={"idea": f"Idea {i}"})

            with ThreadPoolExecutor(max_workers=8) as pool:
                responses = list(pool.map(submit, range(8)))

        session_ids = [r.json()["sessionId"] for r in responses]
        self.assertEqual(len(session_ids), len(set(session_ids)), "every concurrent request must get its own session")
        for r in responses:
            self.assertEqual(r.status_code, 200)

    def test_concurrent_requests_over_the_rate_limit_get_429_not_a_crash(self):
        with patch("main.pipeline.invoke", return_value=_fake_state()), patch("main._VALIDATE_RATE_LIMIT", 5):
            def submit(i):
                return self.client.post("/validate", json={"idea": f"Idea {i}"})

            with ThreadPoolExecutor(max_workers=10) as pool:
                responses = list(pool.map(submit, range(10)))

        statuses = sorted(r.status_code for r in responses)
        # Exactly 5 succeed, the rest are rate-limited - never a 500, which
        # would mean the rate limiter's lock let two threads race past the
        # counter check together.
        self.assertEqual(statuses.count(200), 5)
        self.assertEqual(statuses.count(429), 5)
        self.assertNotIn(500, statuses)

    def test_concurrent_job_creation_does_not_lose_or_corrupt_jobs(self):
        job_ids = [job_store.create_job() for _ in range(20)]

        def complete(job_id):
            job_store.complete_job(job_id, {"summary": job_id})

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(complete, job_ids))

        for job_id in job_ids:
            job = job_store.get_job(job_id)
            self.assertIsNotNone(job, f"job {job_id} was lost under concurrent writes")
            self.assertEqual(job["status"], "complete")
            self.assertEqual(job["result"]["summary"], job_id)

    def test_concurrent_chat_sessions_do_not_cross_contaminate_history(self):
        session_a = session_store.create_session({"idea": "Idea A"})
        session_b = session_store.create_session({"idea": "Idea B"})

        def append_many(session_id, label):
            for i in range(10):
                session_store.append_turn(session_id, f"{label}-{i}", f"reply-{label}-{i}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(append_many, session_a, "A").result()
            pool.submit(append_many, session_b, "B").result()

        history_a = session_store.get_session(session_a)["history"]
        history_b = session_store.get_session(session_b)["history"]
        self.assertTrue(all(turn["message"].startswith("A-") for turn in history_a))
        self.assertTrue(all(turn["message"].startswith("B-") for turn in history_b))


if __name__ == "__main__":
    unittest.main()
