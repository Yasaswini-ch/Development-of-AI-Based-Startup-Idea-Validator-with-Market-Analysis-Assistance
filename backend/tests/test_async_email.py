"""Tests for the async validation + email-on-completion path (main.py) and
its supporting modules: job_store.py and email_delivery.py.

Uses FastAPI's TestClient (httpx-based) since these tests exercise the HTTP
contract directly - status codes (202 processing, 502 job failure) and the
job-polling endpoint aren't reachable by calling the graph/agent functions
directly, unlike test_milestone2.py/test_milestone3.py.
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import email_delivery, job_store


def _fake_state(**overrides):
    state = {
        "summary": "A promising idea.",
        "results": [],
        "confidence": {"agreement": 1.0},
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


class AsyncValidationTests(unittest.TestCase):
    def setUp(self):
        main._clear_cache()
        main._clear_rate_limits()
        job_store.clear_jobs()
        self.client = TestClient(main.app)

    def test_email_field_rejects_invalid_address(self):
        response = self.client.post(
            "/validate",
            json={"idea": "Idea", "email": "not-an-email"},
        )
        self.assertEqual(response.status_code, 422)

    @patch("main.pipeline.invoke", return_value=_fake_state())
    def test_fast_completion_returns_full_response_even_with_email(self, _invoke):
        response = self.client.post(
            "/validate",
            json={"idea": "Idea", "email": "founder@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sessionId", data)
        self.assertEqual(data["summary"], "A promising idea.")

    @patch("main._ASYNC_EMAIL_THRESHOLD_SECONDS", 0.05)
    @patch("main.send_report_email", return_value=True)
    def test_slow_pipeline_with_email_returns_processing_then_completes(self, send_email):
        def slow_invoke(_state):
            time.sleep(0.2)
            return _fake_state()

        # The background task that finishes the pipeline after /validate
        # already responded only keeps running across requests if the
        # underlying event loop stays alive between them - using TestClient
        # as a context manager keeps one loop/portal open for every request
        # made inside the `with` block, matching how a real long-lived
        # uvicorn process behaves (a bare TestClient() call spins up and
        # tears down its own loop per request, which would cancel the
        # detached task before it ever finishes).
        with patch("main.pipeline.invoke", side_effect=slow_invoke), TestClient(main.app) as client:
            response = client.post(
                "/validate",
                json={"idea": "Slow idea", "email": "founder@example.com"},
            )
            self.assertEqual(response.status_code, 202)
            body = response.json()
            self.assertEqual(body["status"], "processing")
            job_id = body["jobId"]

            # Give the detached background task time to finish and store
            # the result - this test's whole point is that finishing
            # doesn't depend on the original request still being open.
            status = {"status": "processing"}
            for _ in range(20):
                status = client.get(f"/validate/status/{job_id}").json()
                if status["status"] != "processing":
                    break
                time.sleep(0.05)

        self.assertEqual(status["status"], "complete")
        self.assertEqual(status["summary"], "A promising idea.")
        send_email.assert_called_once()

    def test_slow_pipeline_without_email_stays_synchronous(self):
        def slow_invoke(_state):
            time.sleep(0.1)
            return _fake_state()

        with patch("main._ASYNC_EMAIL_THRESHOLD_SECONDS", 0.02), patch(
            "main.pipeline.invoke", side_effect=slow_invoke
        ):
            response = self.client.post("/validate", json={"idea": "No email idea"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"], "A promising idea.")

    @patch("main.pipeline.invoke", return_value=_fake_state(error="Every source failed."))
    def test_pipeline_state_error_returns_502(self, _invoke):
        response = self.client.post("/validate", json={"idea": "Idea"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("Every source failed", response.json()["error"])

    def test_unknown_job_returns_404(self):
        response = self.client.get("/validate/status/does-not-exist")
        self.assertEqual(response.status_code, 404)

    @patch("main.pipeline.invoke", return_value=_fake_state())
    def test_validate_rate_limit_returns_429(self, _invoke):
        with patch("main._VALIDATE_RATE_LIMIT", 2):
            first = self.client.post("/validate", json={"idea": "Idea one"})
            second = self.client.post("/validate", json={"idea": "Idea two"})
            third = self.client.post("/validate", json={"idea": "Idea three"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)
        self.assertIn("Too many validation requests", third.json()["error"])

    def test_export_pdf_rejects_malformed_shape(self):
        # marketOpportunity must be an object, not a bare string - this
        # should fail Pydantic validation (422) before ever reaching
        # generate_dossier_pdf/ReportLab.
        response = self.client.post("/export-pdf", json={"idea": "Idea", "marketOpportunity": "not an object"})
        self.assertEqual(response.status_code, 422)

    def test_export_pdf_accepts_a_real_validate_response_shape(self):
        response = self.client.post("/export-pdf", json=_fake_state())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        job_store.clear_jobs()

    def test_job_lifecycle(self):
        job_id = job_store.create_job()
        self.assertEqual(job_store.get_job(job_id)["status"], "processing")

        job_store.complete_job(job_id, {"summary": "done"})
        job = job_store.get_job(job_id)
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["result"]["summary"], "done")

    def test_failed_job(self):
        job_id = job_store.create_job()
        job_store.fail_job(job_id, "boom")
        job = job_store.get_job(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "boom")

    def test_unknown_job_returns_none(self):
        self.assertIsNone(job_store.get_job("missing"))


class EmailDeliveryTests(unittest.TestCase):
    def test_valid_email_addresses(self):
        self.assertTrue(email_delivery.is_valid_email("founder@example.com"))
        self.assertFalse(email_delivery.is_valid_email("not-an-email"))
        self.assertFalse(email_delivery.is_valid_email(""))

    def test_send_without_api_key_returns_false(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("RESEND_API_KEY", None)
            sent = email_delivery.send_report_email(
                "founder@example.com", "Idea", {"summary": "Test"}
            )
        self.assertFalse(sent)

    def test_send_rejects_invalid_recipient_even_with_key(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": "test-key"}):
            sent = email_delivery.send_report_email("not-an-email", "Idea", {"summary": "Test"})
        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
