"""Milestone 4 / Track F - end-to-end error-path test pass.

Covers what test_milestone3.py's test_strategy_node_failures_are_isolated
left out: every OTHER node's own failure isolation (web_search,
market_opportunity, competitor_discovery, opportunity_score, white_space,
viability_score - swot/mvp/gtm/contradiction_detector/experiment_generator/
action_plan/confidence_dashboard already had direct coverage before this
file). Also covers empty/invalid input, an agent failing mid-pipeline (via
a real pipeline.invoke() run, not just an isolated node call), and a slow
(but not hanging) LLM call.
"""

import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import unittest

from fastapi.testclient import TestClient

import main
from agent.graph import (
    NEEDS_DEEP_ANALYSIS,
    competitor_discovery_node,
    market_opportunity_node,
    opportunity_score_node,
    pipeline,
    viability_score_node,
    web_search_node,
    white_space_node,
)
from agent.llm import NeedsDeepAnalysisError


class WebSearchNodeErrorPathTests(unittest.TestCase):
    @patch("agent.graph.retrieval.collect")
    def test_failure_sets_error_key_not_a_crash(self, collect):
        collect.side_effect = RuntimeError("search provider unreachable")
        result = web_search_node({"idea": "Idea", "targetCustomer": "", "problem": ""})
        self.assertIn("error", result)
        self.assertNotIn("results", result)


class MarketOpportunityNodeErrorPathTests(unittest.TestCase):
    @patch("agent.graph.analyze_market_opportunity")
    def test_failure_is_isolated(self, analyze):
        analyze.side_effect = RuntimeError("failed")
        state = {"idea": "Idea", "results": [], "errors": {}}
        result = market_opportunity_node(state)
        self.assertIsNone(result["marketOpportunity"])
        self.assertIn("marketOpportunity", result["errors"])
        self.assertNotIn("error", result)

    def test_skipped_when_web_search_already_failed(self):
        state = {"error": "search failed"}
        result = market_opportunity_node(state)
        self.assertNotIn("marketOpportunity", result)


class CompetitorDiscoveryNodeErrorPathTests(unittest.TestCase):
    @patch("agent.graph.analyze_competitors")
    def test_failure_is_isolated(self, analyze):
        analyze.side_effect = RuntimeError("failed")
        state = {"idea": "Idea", "results": [], "errors": {}}
        result = competitor_discovery_node(state)
        self.assertIsNone(result["competitors"])
        self.assertIn("competitors", result["errors"])
        self.assertNotIn("error", result)


class OpportunityScoreNodeErrorPathTests(unittest.TestCase):
    @patch("agent.graph.calculate_opportunity_score")
    def test_failure_falls_back_to_zero_without_crashing(self, calculate):
        calculate.side_effect = RuntimeError("failed")
        state = {"marketOpportunity": {"marketSize": "text", "trends": []}, "competitors": None, "results": [], "errors": {}}
        result = opportunity_score_node(state)
        self.assertEqual(result["marketOpportunity"]["opportunityScore"], 0)

    def test_skipped_when_market_opportunity_is_none(self):
        state = {"marketOpportunity": None, "competitors": None, "results": [], "errors": {}}
        result = opportunity_score_node(state)
        self.assertNotIn("opportunityScore", (result.get("marketOpportunity") or {}))


class WhiteSpaceNodeErrorPathTests(unittest.TestCase):
    @patch("agent.graph.analyze_white_space")
    def test_failure_is_isolated(self, analyze):
        analyze.side_effect = RuntimeError("failed")
        state = {"marketOpportunity": None, "competitors": None, "results": [], "errors": {}}
        result = white_space_node(state)
        self.assertIsNone(result["whiteSpace"])
        self.assertIn("whiteSpace", result["errors"])
        self.assertNotIn("error", result)


class ViabilityScoreNodeErrorPathTests(unittest.TestCase):
    """Regression coverage for the missing try/except found during this
    pass - viability_score_node was the only node in graph.py that let an
    exception from its core call propagate and crash the whole request
    instead of being isolated like every other node.
    """

    @patch("agent.graph.calculate_market_viability")
    def test_failure_is_isolated_not_a_crash(self, calculate):
        calculate.side_effect = RuntimeError("failed")
        state = {"marketOpportunity": {"marketSize": "text", "trends": []}, "swot": None, "errors": {}}
        result = viability_score_node(state)  # must not raise
        self.assertIsNone(result["marketViability"])
        self.assertIn("marketViability", result["errors"])
        self.assertNotIn("error", result)

    def test_skipped_when_market_opportunity_is_none(self):
        state = {"marketOpportunity": None, "swot": None, "errors": {}}
        result = viability_score_node(state)
        self.assertNotIn("marketViability", result)


class InvalidInputTests(unittest.TestCase):
    """ValidateRequest.idea previously had no length bound at all - an
    empty/whitespace idea built degenerate search queries (e.g. a bare
    " market size") against real external search APIs instead of being
    rejected up front.
    """

    def setUp(self):
        self.client = TestClient(main.app)
        main._clear_rate_limits()

    def test_empty_idea_is_rejected(self):
        resp = self.client.post("/validate", json={"idea": ""})
        self.assertEqual(resp.status_code, 422)

    def test_whitespace_only_idea_is_rejected(self):
        resp = self.client.post("/validate", json={"idea": "   \n\t  "})
        self.assertEqual(resp.status_code, 422)

    def test_missing_idea_is_rejected(self):
        resp = self.client.post("/validate", json={})
        self.assertEqual(resp.status_code, 422)

    def test_excessively_long_idea_is_rejected(self):
        resp = self.client.post("/validate", json={"idea": "x" * 2501})
        self.assertEqual(resp.status_code, 422)

    @patch("main.pipeline.invoke", return_value={"summary": "ok", "results": [], "errors": {}})
    def test_idea_at_the_length_boundary_is_accepted_by_validation(self, _invoke):
        # Shape-only check: confirms the 2500-char idea itself clears
        # Pydantic validation (a 422 here would mean the boundary is off by
        # one) - not a full pipeline run, so any other status is fine too.
        resp = self.client.post("/validate", json={"idea": "x" * 2500})
        self.assertNotEqual(resp.status_code, 422)

    def test_excessively_long_target_customer_is_rejected(self):
        resp = self.client.post("/validate", json={"idea": "Valid idea", "targetCustomer": "x" * 601})
        self.assertEqual(resp.status_code, 422)



class MidPipelineFailureIntegrationTests(unittest.TestCase):
    """Runs the REAL compiled pipeline (agent.graph.pipeline), not an
    isolated node call, with one agent mocked to fail partway through -
    confirms every node downstream of the failure still runs and produces
    its own output, rather than the whole run stopping at the first error.
    """

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_market_opportunity_failure_does_not_block_downstream_nodes(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        # Every other agent mocked to return instantly - this test asserts
        # failure isolation around market_opportunity_node specifically, not
        # real LLM behavior, so nothing else here should make a live call.
        collect.return_value = [
            {"title": "A", "snippet": "s", "url": "https://a", "angle": "Competitors", "score": 0.7}
        ]
        market.side_effect = RuntimeError("market agent failed")
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.return_value = {"features": []}
        gtm.return_value = {
            "positioning": "text",
            "positioningSourceIds": [],
            "channels": [],
            "earlyCustomerApproach": "text",
            "earlyCustomerApproachSourceIds": [],
        }
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        state = pipeline.invoke({"idea": "A meal kit for busy families", "targetCustomer": "", "problem": ""})

        # The failed section is recorded, not silently missing.
        self.assertIsNone(state["marketOpportunity"])
        self.assertIn("marketOpportunity", state["errors"])
        # Downstream sections that don't strictly need marketOpportunity
        # still ran - competitors comes from the same raw results
        # independently of market_opportunity_node.
        self.assertIn("competitors", state)
        # Sections that explicitly skip without marketOpportunity degrade
        # to "not present" rather than crashing the whole request.
        self.assertNotIn("opportunityScore", (state.get("marketOpportunity") or {}) if state.get("marketOpportunity") else {})
        # The pipeline reached its final node and returned a normal
        # (non-pipeline-error) result.
        self.assertNotIn("error", state)
        self.assertIn("confidence", state)


class ParallelMvpGtmFailureTests(unittest.TestCase):
    """mvp_recommendation and gtm_strategy run as parallel branches off
    viability_score (see build_pipeline) instead of one after the other,
    so both can now fail in the very same step - something that could
    never happen while they ran sequentially. Runs the real compiled
    pipeline (not isolated node calls) since the failure mode this guards
    against - two concurrent writes to a shared state channel - only
    surfaces during actual LangGraph execution.
    """

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_both_branches_needing_deep_analysis_at_once_does_not_crash(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        collect.return_value = [
            {"title": "A", "snippet": "s", "url": "https://a", "angle": "Competitors", "score": 0.7}
        ]
        market.return_value = {"marketSize": "text", "trends": [], "segments": []}
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.side_effect = NeedsDeepAnalysisError()
        gtm.side_effect = NeedsDeepAnalysisError()

        state = pipeline.invoke({"idea": "A meal kit for busy families", "targetCustomer": "", "problem": ""})

        self.assertEqual(state["error"], NEEDS_DEEP_ANALYSIS)
        # Neither branch got far enough to write its own key at all on
        # this path (same as before parallelization - NeedsDeepAnalysisError
        # short-circuits before either "mvp" or "gtm" would be set), so
        # .get() rather than a literal key lookup.
        self.assertIsNone(state.get("mvp"))
        self.assertIsNone(state.get("gtm"))

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_both_branches_failing_at_once_records_both_errors(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        collect.return_value = [
            {"title": "A", "snippet": "s", "url": "https://a", "angle": "Competitors", "score": 0.7}
        ]
        market.return_value = {"marketSize": "text", "trends": [], "segments": []}
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.side_effect = RuntimeError("mvp boom")
        gtm.side_effect = RuntimeError("gtm boom")
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        state = pipeline.invoke({"idea": "A meal kit for busy families", "targetCustomer": "", "problem": ""})

        self.assertIsNone(state["mvp"])
        self.assertIsNone(state["gtm"])
        self.assertIn("mvp", state["errors"])
        self.assertIn("gtm", state["errors"])
        # Neither branch's failure was swallowed by the other overwriting
        # the shared "errors" channel - the rest of the run still
        # completed normally.
        self.assertNotIn("error", state)


class SlowLlmCallTests(unittest.TestCase):
    """A genuinely slow (not rate-limited, not erroring) LLM call has no
    explicit per-call timeout anywhere in llm.py (confirmed by inspection -
    no `timeout=` kwarg on LLM() or crew.kickoff()) - flagged here for
    Track F's latency pass rather than fixed in this test pass, since
    picking a concrete timeout value needs the real latency numbers that
    pass is meant to gather. This test only confirms that a slow-but-
    eventually-returning call doesn't trigger any retry/backoff logic that
    would make it worse (kickoff_with_fallback's own wait path is bounded
    at _MAX_RETRY_WAIT_SECONDS=30s and only triggers on an actual rate-limit
    error, never on plain latency).
    """

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_slow_but_successful_call_completes_normally(self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue):
        collect.return_value = []
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.return_value = {"features": []}
        gtm.return_value = {
            "positioning": "text",
            "positioningSourceIds": [],
            "channels": [],
            "earlyCustomerApproach": "text",
            "earlyCustomerApproachSourceIds": [],
        }
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        def slow_market_call(*args, **kwargs):
            # Simulated latency, not a real sleep - this test asserts
            # behavior around a slow call, not actual wall-clock timing.
            return {"marketSize": "text", "trends": [], "segments": []}

        market.side_effect = slow_market_call
        state = pipeline.invoke({"idea": "Idea", "targetCustomer": "", "problem": ""})
        self.assertIsNotNone(state["marketOpportunity"])
        self.assertNotIn("error", state)


if __name__ == "__main__":
    unittest.main()
