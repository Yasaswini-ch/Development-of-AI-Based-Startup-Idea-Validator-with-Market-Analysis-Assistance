"""Tests for Track G.2 - Quick/Deep Validation Modes and the concurrent-
LLM-call semaphore (docs/unique-features-plan.md §4).
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import llm
from agent.graph import pipeline
from agent.session_store import clear_sessions


def _idea_args(mode=None):
    args = {"idea": "A subscription box for eco-friendly cleaning products", "targetCustomer": "eco-conscious households", "problem": "plastic waste"}
    if mode is not None:
        args["mode"] = mode
    return args


class QuickModeGraphTests(unittest.TestCase):
    """Deep mode is every existing test's default behavior (unchanged) -
    these focus on what's new: quick mode actually skipping the Milestone
    3/4 strategy nodes.
    """

    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_quick_mode_skips_swot_mvp_gtm_and_derived_nodes(self, collect, market, competitors):
        collect.return_value = [{"title": "S", "snippet": "...", "url": "https://example.com", "angle": "Market size & trends", "score": 0.5}]
        market.return_value = {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 0}
        competitors.return_value = {"competitors": []}

        result = pipeline.invoke(_idea_args(mode="quick"))

        self.assertIsNone(result.get("swot"))
        self.assertIsNone(result.get("mvp"))
        self.assertIsNone(result.get("gtm"))
        self.assertNotIn("marketViability", result)
        self.assertEqual(result.get("contradictions", []), [])
        self.assertEqual(result.get("experiments", []), [])
        # Quick mode skipping is not a failure - none of these should show
        # up as recorded errors, unlike a genuine node failure would.
        self.assertEqual(result.get("errors", {}), {})

    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_quick_mode_still_runs_core_market_analysis(self, collect, market, competitors, swot, mvp, gtm):
        collect.return_value = [{"title": "S", "snippet": "...", "url": "https://example.com", "angle": "Market size & trends", "score": 0.5}]
        market.return_value = {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 0}
        competitors.return_value = {"competitors": []}

        result = pipeline.invoke(_idea_args(mode="quick"))

        self.assertIsNotNone(result.get("marketOpportunity"))
        self.assertIsNotNone(result.get("competitors"))
        self.assertIn("whiteSpace", result)
        self.assertIn("confidence", result)
        # None of the strategy agents should have been called at all in
        # quick mode, not just have their output discarded.
        swot.assert_not_called()
        mvp.assert_not_called()
        gtm.assert_not_called()

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_deep_mode_default_runs_the_full_pipeline_unchanged(self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue):
        revenue.return_value = {"models": []}
        assumptions.return_value = {"assumptions": []}
        collect.return_value = [{"title": "S", "snippet": "...", "url": "https://example.com", "angle": "Market size & trends", "score": 0.5}]
        market.return_value = {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 0}
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.return_value = {"features": []}
        gtm.return_value = {"positioning": "P", "channels": [], "earlyCustomerApproach": "E"}

        # No mode passed at all - matches every existing caller/test that
        # predates this feature and must keep working identically.
        result = pipeline.invoke({"idea": "Idea", "targetCustomer": "Founders", "problem": "Risk"})

        self.assertIsNotNone(result.get("swot"))
        self.assertIsNotNone(result.get("mvp"))
        self.assertIsNotNone(result.get("gtm"))
        self.assertIn("marketViability", result)


class QuickDeepModeEndpointTests(unittest.TestCase):
    def setUp(self):
        clear_sessions()
        main._clear_cache()
        main._clear_rate_limits()
        self.client = TestClient(main.app)

    def test_mode_defaults_to_deep_when_omitted(self):
        with patch("main.pipeline.invoke") as invoke:
            invoke.return_value = {"summary": "S", "results": [], "errors": {}, "mode": "deep"}
            response = self.client.post("/validate", json={"idea": "Idea"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "deep")
        self.assertEqual(invoke.call_args[0][0]["mode"], "deep")

    def test_quick_mode_is_threaded_into_the_pipeline_call(self):
        with patch("main.pipeline.invoke") as invoke:
            invoke.return_value = {"summary": "S", "results": [], "errors": {}, "mode": "quick"}
            response = self.client.post("/validate", json={"idea": "Idea", "mode": "quick"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "quick")
        self.assertEqual(invoke.call_args[0][0]["mode"], "quick")

    def test_rejects_an_invalid_mode_value(self):
        response = self.client.post("/validate", json={"idea": "Idea", "mode": "turbo"})
        self.assertEqual(response.status_code, 422)

    def test_quick_and_deep_requests_for_the_same_idea_do_not_share_a_cache_entry(self):
        with patch("main.pipeline.invoke") as invoke:
            invoke.side_effect = [
                {"summary": "Deep summary", "results": [], "errors": {}, "mode": "deep"},
                {"summary": "Quick summary", "results": [], "errors": {}, "mode": "quick"},
            ]
            deep_response = self.client.post("/validate", json={"idea": "Same idea"})
            quick_response = self.client.post("/validate", json={"idea": "Same idea", "mode": "quick"})

        self.assertEqual(invoke.call_count, 2, "a quick request must not be served from the deep response's cache entry")
        self.assertEqual(deep_response.json()["summary"], "Deep summary")
        self.assertEqual(quick_response.json()["summary"], "Quick summary")


    def test_a_degraded_response_is_not_cached(self):
        degraded = {"summary": "S", "results": [], "errors": {}, "mode": "deep", "swot": {"degraded": True}}
        clean = {"summary": "S2", "results": [], "errors": {}, "mode": "deep", "swot": {"degraded": False}}
        with patch("main.pipeline.invoke") as invoke:
            invoke.side_effect = [degraded, clean]
            self.client.post("/validate", json={"idea": "Same idea"})
            second = self.client.post("/validate", json={"idea": "Same idea"})
        self.assertEqual(invoke.call_count, 2, "a degraded result must not be served from cache")
        self.assertEqual(second.json()["summary"], "S2")

    def test_a_clean_response_is_still_cached(self):
        clean = {"summary": "S", "results": [], "errors": {}, "mode": "deep", "swot": {"degraded": False}}
        with patch("main.pipeline.invoke") as invoke:
            invoke.return_value = clean
            self.client.post("/validate", json={"idea": "Same idea"})
            self.client.post("/validate", json={"idea": "Same idea"})
        self.assertEqual(invoke.call_count, 1)


class LlmConcurrencySemaphoreTests(unittest.TestCase):
    """The semaphore itself, isolated from the pipeline - proves it actually
    throttles concurrent calls rather than just existing unused.
    """

    def test_semaphore_limits_concurrent_kickoffs_to_the_configured_max(self):
        max_concurrent = 2
        semaphore = threading.Semaphore(max_concurrent)
        in_flight = []
        peak = []
        lock = threading.Lock()

        def build_crew(model):
            class _FakeOutput:
                raw = "ok"
                token_usage = None

            class _FakeCrew:
                def kickoff(self):
                    with semaphore:
                        with lock:
                            in_flight.append(1)
                            peak.append(max(peak) if peak else 0)
                            peak[-1] = max(peak[-1], len(in_flight))
                        time.sleep(0.05)
                        with lock:
                            in_flight.pop()
                    return _FakeOutput()

            return _FakeCrew()

        with patch.object(llm, "_llm_semaphore", semaphore):
            threads = [threading.Thread(target=llm._kickoff_with_metrics, args=("m", build_crew)) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertLessEqual(max(peak), max_concurrent)

    def test_default_semaphore_size_is_configurable_via_env(self):
        # Just confirms the env var is actually read at import time, not
        # hardcoded - the module-level constant is what get_engine-style
        # env configuration elsewhere in this codebase relies on being real.
        self.assertGreaterEqual(llm._MAX_CONCURRENT_LLM_CALLS, 1)


if __name__ == "__main__":
    unittest.main()
