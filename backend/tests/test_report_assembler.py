"""Tests for the Milestone 4 Track D canonical report: report_assembler.py
and its two HTTP endpoints (GET /reports/{sessionId}, POST
/reports/{sessionId}/email) in main.py.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent.report_assembler import assemble_report, report_to_pdf_input
from agent.session_store import clear_sessions, create_session


def _full_context(**overrides):
    context = {
        "idea": "A subscription box for eco-friendly cleaning products",
        "targetCustomer": "eco-conscious households",
        "problem": "plastic waste",
        "summary": "The market is growing.",
        "sources": [{"sourceId": "src-1", "title": "Report", "url": "https://example.com", "snippet": "...", "angle": "Market size & trends"}],
        "confidence": {"agreeingSources": 1, "totalSources": 1, "percentage": 100},
        "marketOpportunity": {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 70},
        "competitors": {"competitors": []},
        "whiteSpace": {"opportunities": []},
        "swot": {
            "strengths": [{"text": "Focused niche", "sourceIds": ["src-1"]}],
            "weaknesses": [], "opportunities": [], "threats": [], "risks": [],
        },
        "mvp": {"features": []},
        "gtm": {"positioning": "Eco-first", "channels": [], "earlyCustomerApproach": "Interviews"},
    }
    context.update(overrides)
    return context


class ReportAssemblerTests(unittest.TestCase):
    def test_assembles_the_canonical_shape_from_a_full_context(self):
        report = assemble_report("session-1", _full_context())

        self.assertEqual(report["sessionId"], "session-1")
        self.assertTrue(report["reportId"])
        self.assertEqual(report["ideaSummary"]["idea"], "A subscription box for eco-friendly cleaning products")
        self.assertEqual(report["opportunityScore"], 70)
        self.assertEqual(report["gtm"]["positioning"], "Eco-first")
        self.assertEqual(report["sectionErrors"], {})
        self.assertEqual(report["degradedSections"], [])
        self.assertEqual(report["contradictions"], [])
        self.assertEqual(report["experiments"], [])
        self.assertTrue(report["generatedAt"])

    def test_missing_sections_are_recorded_as_section_errors_not_silently_dropped(self):
        context = _full_context(marketOpportunity=None, gtm=None)
        report = assemble_report("session-2", context)

        self.assertIsNone(report["marketOpportunity"])
        self.assertIsNone(report["gtm"])
        self.assertIn("marketOpportunity", report["sectionErrors"])
        self.assertIn("gtm", report["sectionErrors"])
        self.assertNotIn("swot", report["sectionErrors"])
        # opportunityScore falls back to 0 when marketOpportunity itself is None,
        # rather than raising on a missing dict.
        self.assertEqual(report["opportunityScore"], 0)

    def test_degraded_sections_are_flagged_separately_from_missing_ones(self):
        context = _full_context(swot={**_full_context()["swot"], "degraded": True})
        report = assemble_report("session-3", context)

        self.assertEqual(report["degradedSections"], ["swot"])
        self.assertEqual(report["sectionErrors"], {})  # degraded is not the same as missing

    def test_picks_up_contradictions_and_experiments_once_tracks_b_c_land(self):
        # Simulates what happens automatically once contradiction_detector.py/
        # experiment_generator.py/action_plan.py start writing these keys into
        # session context - no report_assembler.py change needed for this.
        context = _full_context(
            contradictions=[{"type": "growth_vs_demand", "detail": "..."}],
            experiments=[{"hypothesis": "..."}],
            actionPlan={"next7Days": "..."},
        )
        report = assemble_report("session-4", context)

        self.assertEqual(len(report["contradictions"]), 1)
        self.assertEqual(len(report["experiments"]), 1)
        self.assertEqual(report["actionPlan"]["next7Days"], "...")

    def test_report_to_pdf_input_flattens_ideasummary_back_to_the_shape_pdf_exporter_expects(self):
        report = assemble_report("session-5", _full_context())
        pdf_input = report_to_pdf_input(report)

        self.assertEqual(pdf_input["idea"], "A subscription box for eco-friendly cleaning products")
        self.assertEqual(pdf_input["summary"], "The market is growing.")
        self.assertEqual(pdf_input["gtm"]["positioning"], "Eco-first")


class ReportEndpointTests(unittest.TestCase):
    def setUp(self):
        clear_sessions()
        main._clear_rate_limits()
        self.client = TestClient(main.app)

    def test_get_report_returns_404_for_unknown_session(self):
        response = self.client.get("/reports/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_get_report_returns_the_canonical_shape_for_a_real_session(self):
        session_id = create_session(_full_context())
        response = self.client.get(f"/reports/{session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sessionId"], session_id)
        self.assertEqual(body["gtm"]["positioning"], "Eco-first")

    def test_email_report_returns_404_for_unknown_session(self):
        response = self.client.post("/reports/does-not-exist/email", json={"recipient": "founder@example.com"})
        self.assertEqual(response.status_code, 404)

    def test_email_report_rejects_an_invalid_recipient(self):
        session_id = create_session(_full_context())
        response = self.client.post(f"/reports/{session_id}/email", json={"recipient": "not-an-email"})
        self.assertEqual(response.status_code, 422)

    @patch("main.send_canonical_report_email", return_value=True)
    def test_email_report_returns_202_and_a_delivery_id_on_success(self, send_email):
        session_id = create_session(_full_context())
        response = self.client.post(f"/reports/{session_id}/email", json={"recipient": "founder@example.com"})

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "queued")
        self.assertTrue(body["deliveryId"])
        send_email.assert_called_once()
        # Never reruns retrieval/any agent - only the already-stored session
        # context and a PDF render happen in this path.

    @patch("main.send_canonical_report_email", return_value=False)
    def test_email_report_returns_502_when_delivery_fails(self, _send_email):
        session_id = create_session(_full_context())
        response = self.client.post(f"/reports/{session_id}/email", json={"recipient": "founder@example.com"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["status"], "failed")


if __name__ == "__main__":
    unittest.main()
