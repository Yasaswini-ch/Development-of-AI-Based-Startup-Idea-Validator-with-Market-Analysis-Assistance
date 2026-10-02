"""Tests for agent/metrics.py and GET /metrics - the counters that answer
docs/api-cost-accuracy-performance-metrics.md's §7 "Open Metrics" questions
(cache hit rate, per-node LLM success/failure rate) that doc flagged as not
yet measured.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("WEB_CACHE", "0")  # tests must never read or write the shared lookup cache (agent/web_cache.py)
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import metrics


class MetricsModuleTests(unittest.TestCase):
    def setUp(self):
        metrics.reset()

    def test_increment_starts_a_counter_at_one(self):
        metrics.increment("node.swot.success")
        self.assertEqual(metrics.snapshot()["node.swot.success"], 1)

    def test_increment_accumulates_across_calls(self):
        for _ in range(3):
            metrics.increment("cache.hit")
        self.assertEqual(metrics.snapshot()["cache.hit"], 3)

    def test_snapshot_only_contains_keys_actually_incremented(self):
        metrics.increment("cache.hit")
        self.assertNotIn("cache.miss", metrics.snapshot())

    def test_snapshot_is_a_copy_not_a_live_reference(self):
        metrics.increment("cache.hit")
        snap = metrics.snapshot()
        metrics.increment("cache.hit")
        self.assertEqual(snap["cache.hit"], 1, "snapshot() must not mutate after being returned")


class MetricsEndpointTests(unittest.TestCase):
    def setUp(self):
        metrics.reset()
        main._clear_cache()
        main._clear_rate_limits()
        self.client = TestClient(main.app)

    def test_metrics_endpoint_returns_empty_object_with_no_activity(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})

    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_a_cache_miss_then_hit_is_reflected_in_metrics(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        collect.return_value = [{"title": "S", "snippet": "...", "url": "https://example.com", "angle": "Market size & trends", "score": 0.5}]
        market.return_value = {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 0}
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.return_value = {"features": []}
        gtm.return_value = {"positioning": "P", "channels": [], "earlyCustomerApproach": "E"}
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        self.client.post("/validate", json={"idea": "Same idea"})
        self.client.post("/validate", json={"idea": "Same idea"})

        body = self.client.get("/metrics").json()
        self.assertEqual(body.get("cache.miss"), 1)
        self.assertEqual(body.get("cache.hit"), 1)
        self.assertEqual(body.get("node.swot.success"), 1)
        self.assertEqual(body.get("node.mvp.success"), 1)
        self.assertEqual(body.get("node.gtm.success"), 1)

    # Every LLM-backed step is patched, not just the ones under test: the steps
    # after swot (MVP, GTM, assumptions, revenue models) still run in the graph,
    # and left unpatched they made real Groq/Gemini calls with the keys in .env
    # every time the suite ran, spending the free quota the app itself needs.
    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot", side_effect=RuntimeError("down"))
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_a_node_failure_increments_the_failure_counter_not_success(
        self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue
    ):
        collect.return_value = [{"title": "S", "snippet": "...", "url": "https://example.com", "angle": "Market size & trends", "score": 0.5}]
        market.return_value = {"marketSize": "Growing", "trends": [], "segments": [], "opportunityScore": 0}
        competitors.return_value = {"competitors": []}
        mvp.return_value = {"features": []}
        gtm.return_value = {"positioning": "P", "channels": [], "earlyCustomerApproach": "E"}
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        self.client.post("/validate", json={"idea": "Idea"})

        body = self.client.get("/metrics").json()
        self.assertEqual(body.get("node.swot.failure"), 1)
        self.assertNotIn("node.swot.success", body)


if __name__ == "__main__":
    unittest.main()
