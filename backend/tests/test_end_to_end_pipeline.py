"""Milestone 4 Track F - full end-to-end and partial-failure-path coverage
across the *entire* current pipeline (every node in graph.py, not just the
Milestone 3-era subset test_milestone3.py's own full-pipeline test covers).

Two concerns, kept separate from the per-agent unit tests elsewhere:

1. Happy path: with every LLM/search call mocked, does a single
   pipeline.invoke() actually populate every node's output key - including
   the newer ones (marketViability, contradictions, experiments,
   actionPlan) that landed after that earlier test was written?

2. Full-failure path: if every LLM-backed analyze_*() call raises, does the
   pipeline still complete without crashing, with every failed section
   recorded in `errors` and no earlier valid artifact erased? This is the
   "partial-failure-path... not just the happy path" coverage called out
   as still open in Track F.

A third block walks one HTTP user journey end to end (validate -> fetch the
canonical report -> email it -> download its PDF -> compare it against a
second session) the way a real founder session would actually use the app,
which no existing test exercises as one continuous flow.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import job_store, session_store
from agent.graph import pipeline


def _idea_args():
    return {"idea": "A subscription box for eco-friendly cleaning products", "targetCustomer": "eco-conscious households", "problem": "plastic waste"}


class FullPipelineHappyPathTests(unittest.TestCase):
    """Every node in the current graph, exercised together in one run."""

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_every_pipeline_node_populates_its_output_key(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        collect.return_value = [
            {
                "title": "Demand grows",
                "snippet": "Demand is growing quickly among busy households.",
                "url": "https://example.com/a",
                "angle": "Market size & trends",
                "score": 0.8,
                "sourceId": "src-1",
            }
        ]
        market.return_value = {
            "marketSize": "Growing niche, USD 2B",
            "trends": ["Rising demand for eco-friendly products"],
            "segments": [
                {
                    "segment": "Eco-conscious households",
                    "painPoints": "Plastic waste guilt",
                    "motivations": "Reduce environmental footprint",
                    "buyingBehavior": "Research online before buying",
                }
            ],
            "opportunityScore": 0,
        }
        competitors.return_value = {"competitors": []}
        swot.return_value = {
            "strengths": [{"text": "Focused niche", "sourceIds": ["src-1"]}],
            "weaknesses": [{"text": "Unproven demand", "sourceIds": []}],
            "opportunities": [{"text": "Growing market", "sourceIds": ["src-1"]}],
            "threats": [{"text": "Established rivals", "sourceIds": []}],
            "risks": [
                {"risk": "Customers may not pay a premium", "severity": "high", "likelihood": "medium", "sourceIds": ["src-1"]}
            ],
        }
        mvp.return_value = {
            "features": [
                {"feature": "Subscription box builder", "priority": "high", "effort": "low", "sourceIds": []}
            ]
        }
        gtm.return_value = {
            "positioning": "Evidence-first eco subscriptions",
            "channels": [{"channel": "Instagram ads", "sourceIds": []}],
            "earlyCustomerApproach": "Direct outreach to eco communities",
        }
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        result = pipeline.invoke(_idea_args())

        # Every node in the current graph writes one of these keys; a
        # missing key here means a node silently stopped running (or was
        # removed from the graph) without this test noticing.
        for key in (
            "summary",
            "results",
            "confidence",
            "marketOpportunity",
            "competitors",
            "whiteSpace",
            "swot",
            "marketViability",
            "mvp",
            "gtm",
            "contradictions",
            "experiments",
            "actionPlan",
        ):
            self.assertIn(key, result, f"pipeline result is missing '{key}' - a node may have stopped running")

        self.assertIsNone(result.get("error"))
        self.assertEqual(result.get("errors", {}), {})
        self.assertGreater(result["marketViability"]["score"], 0)
        self.assertIsInstance(result["experiments"], list)
        self.assertTrue(result["experiments"], "risks were provided but no experiment was generated from them")
        self.assertIn("next7Days", result["actionPlan"])


class FullPipelineFailurePathTests(unittest.TestCase):
    """Every LLM-backed node fails at once - the pipeline must still finish,
    record each failure, and never let one node's exception erase another
    node's already-computed (or intentionally-skipped) artifact.
    """

    @patch("agent.graph.analyze_revenue_models", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.analyze_assumptions", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.analyze_gtm", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.analyze_mvp", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.analyze_swot", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.analyze_competitors", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.analyze_market_opportunity", side_effect=RuntimeError("provider down"))
    @patch("agent.graph.retrieval.collect")
    def test_pipeline_completes_and_records_every_failure_without_crashing(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        collect.return_value = [
            {"title": "Source", "snippet": "...", "url": "https://example.com", "angle": "Market size & trends", "score": 0.5}
        ]

        result = pipeline.invoke(_idea_args())

        # The pipeline itself must not raise/crash - invoke() returning at
        # all (this line executing) is half of what's being tested.
        self.assertIsNone(result.get("error"))

        for section in ("marketOpportunity", "competitors", "swot", "mvp", "gtm"):
            self.assertIsNone(result.get(section))
            self.assertIn(section, result.get("errors", {}), f"{section} failed but was not recorded in errors")

        # Nodes that depend on a failed upstream section must skip
        # themselves cleanly rather than crash on a None input.
        self.assertNotIn("marketViability", result)  # viability_score_node skips when marketOpportunity is None
        self.assertEqual(result.get("contradictions", []), [])
        self.assertEqual(result.get("experiments", []), [])

        # web_search itself still succeeded, so results/summary/confidence
        # must survive even though every downstream analysis node failed -
        # a total LLM outage should not erase what retrieval already found.
        self.assertTrue(result.get("results"))
        self.assertTrue(result.get("summary"))

    @patch("agent.graph.retrieval.collect", side_effect=RuntimeError("search provider down"))
    def test_web_search_failure_is_recorded_and_short_circuits_downstream_nodes(self, collect):
        result = pipeline.invoke(_idea_args())

        self.assertTrue(result.get("error"))
        # Every downstream node checks state.get("error") first and returns
        # the state unchanged - none of them should have produced output.
        for key in ("marketOpportunity", "competitors", "swot", "mvp", "gtm"):
            self.assertIsNone(result.get(key))


class FullUserJourneyHttpTests(unittest.TestCase):
    """One continuous HTTP flow: validate -> read the canonical report ->
    email it -> download its PDF -> compare it against a second session.
    Exercises the endpoints together the way an actual session would use
    them, rather than each in isolation.
    """

    def setUp(self):
        main._clear_cache()
        main._clear_rate_limits()
        job_store.clear_jobs()
        session_store.clear_sessions()
        self.client = TestClient(main.app)

    def _fake_pipeline_result(self, idea_label="Idea A"):
        return {
            "summary": f"{idea_label} looks promising.",
            "results": [{"title": "Source", "url": "https://example.com", "snippet": "...", "angle": "Market size & trends", "sourceId": "src-1"}],
            "confidence": {"agreeingSources": 1, "totalSources": 1, "percentage": 100},
            "marketOpportunity": {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 60},
            "competitors": {"competitors": []},
            "whiteSpace": {"opportunities": []},
            "swot": {"strengths": [{"text": "Focused", "sourceIds": ["src-1"]}], "weaknesses": [], "opportunities": [], "threats": [], "risks": []},
            "marketViability": {"score": 70, "label": "Promising", "marketDemand": 70, "executionRisk": 30, "growthVelocity": 60},
            "mvp": {"features": []},
            "gtm": {"positioning": f"{idea_label} positioning", "channels": [], "earlyCustomerApproach": "Interviews"},
            "contradictions": [],
            "experiments": [],
            "actionPlan": {},
            "assumptions": {"assumptions": [{"assumption": "Founders will pay monthly", "category": "demand", "uncertainty": "high"}]},
            "revenueModels": {"models": [{"name": "SaaS Subscription", "fit": "high"}]},
            "errors": {},
        }

    @patch("main.send_canonical_report_email", return_value=True)
    @patch("main.pipeline.invoke")
    def test_validate_then_report_then_email_then_pdf_then_compare(self, invoke, send_email):
        invoke.return_value = self._fake_pipeline_result("Idea A")
        validate_response = self.client.post("/validate", json={"idea": "A subscription box for eco-friendly cleaning products"})
        self.assertEqual(validate_response.status_code, 200)
        session_id_a = validate_response.json()["sessionId"]

        report_response = self.client.get(f"/reports/{session_id_a}")
        self.assertEqual(report_response.status_code, 200)
        report_body = report_response.json()
        self.assertEqual(report_body["gtm"]["positioning"], "Idea A positioning")
        # Regression: assumptions/revenueModels used to be computed and
        # returned by /validate but dropped before ever reaching a stored
        # session, so a read-back like this always saw them as missing.
        self.assertEqual(len(report_body["assumptions"]["assumptions"]), 1)
        self.assertEqual(report_body["revenueModels"]["models"][0]["name"], "SaaS Subscription")

        email_response = self.client.post(f"/reports/{session_id_a}/email", json={"recipient": "founder@example.com"})
        self.assertEqual(email_response.status_code, 202)
        send_email.assert_called_once()

        pdf_response = self.client.get(f"/validate/{session_id_a}/pdf")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["content-type"], "application/pdf")

        invoke.return_value = self._fake_pipeline_result("Idea B")
        validate_response_b = self.client.post("/validate", json={"idea": "A meal-kit delivery service"})
        session_id_b = validate_response_b.json()["sessionId"]

        compare_response = self.client.post("/reports/compare", json={"sessionIds": [session_id_a, session_id_b]})
        self.assertEqual(compare_response.status_code, 200)
        positionings = {r["gtm"]["positioning"] for r in compare_response.json()["reports"]}
        self.assertEqual(positionings, {"Idea A positioning", "Idea B positioning"})

    @patch("main.pipeline.invoke")
    def test_partial_result_is_still_a_usable_report(self, invoke):
        degraded = self._fake_pipeline_result("Idea C")
        degraded["swot"] = None
        degraded["errors"] = {"swot": "The strategy analysis is temporarily unavailable."}
        invoke.return_value = degraded

        validate_response = self.client.post("/validate", json={"idea": "Idea C"})
        self.assertEqual(validate_response.status_code, 200)
        session_id = validate_response.json()["sessionId"]

        report_response = self.client.get(f"/reports/{session_id}")
        self.assertEqual(report_response.status_code, 200)
        body = report_response.json()
        self.assertIsNone(body["swot"])
        self.assertIn("swot", body["sectionErrors"])
        # The rest of the report must still be intact - a failed optional
        # section degrades gracefully rather than voiding the whole report.
        self.assertEqual(body["gtm"]["positioning"], "Idea C positioning")


if __name__ == "__main__":
    unittest.main()
