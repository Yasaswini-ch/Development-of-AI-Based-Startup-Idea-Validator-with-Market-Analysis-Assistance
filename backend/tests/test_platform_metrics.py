"""Tests for agent/platform_metrics.py's aggregation and the admin role/
endpoint gating it (agent/auth.py's require_admin, GET
/admin/platform-metrics).
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete, update

import main
from agent import events
from agent.auth import signup
from agent.db import get_engine, users_table
from agent.platform_metrics import get_platform_metrics


def _clear_users():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(users_table))


def _promote_to_admin(user_id: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(update(users_table).where(users_table.c.id == user_id).values(is_admin=True))


class PlatformMetricsAggregationTests(unittest.TestCase):
    def setUp(self):
        events.clear()

    def test_cache_hit_rate_and_totals(self):
        events.record("cache_miss")
        events.record("cache_miss")
        events.record("cache_hit")
        result = get_platform_metrics()
        self.assertEqual(result["kpis"]["totalValidations"], 2)
        self.assertAlmostEqual(result["kpis"]["cacheHitRate"], 33.3, places=1)

    def test_api_success_rate_only_counts_llm_backed_nodes(self):
        # metrics.py counters are process-global (not reset by events.clear()),
        # so read the rate as a ratio rather than asserting an absolute count.
        from agent import metrics
        metrics.reset()
        metrics.increment("node.swot.success")
        metrics.increment("node.swot.success")
        metrics.increment("node.swot.failure")
        metrics.increment("node.competitor_discovery.failure")  # not LLM-backed - must not count

        result = get_platform_metrics()
        # 2 success / 3 total across the LLM-backed nodes only - the
        # competitor_discovery failure (spaCy NER, no LLM call) must not
        # dilute this, even though it's still tracked in its own right
        # under nodeSuccessRates (a different, broader metric).
        self.assertAlmostEqual(result["kpis"]["apiSuccessRate"], 66.7, places=1)
        self.assertEqual(result["nodeSuccessRates"]["competitor_discovery"], 0.0)

    def test_node_success_rate_comes_from_the_durable_log_not_process_counters(self):
        # Counters reset on every restart; the events table does not.
        from agent import metrics
        metrics.reset()
        for _ in range(4):
            events.record("node_latency", node="white_space", detail={"seconds": 0.1})
        events.record("pipeline_error", node="white_space", detail={"errorType": "ValueError"})
        result = get_platform_metrics()
        self.assertEqual(result["nodeSuccessRates"]["white_space"], 75.0)

    def test_graph_names_and_short_names_are_counted_together(self):
        # The graph times "swot_analysis" but failures are recorded as "swot".
        from agent import metrics
        metrics.reset()
        for _ in range(2):
            events.record("node_latency", node="swot_analysis", detail={"seconds": 2.0})
        events.record("pipeline_error", node="swot", detail={"errorType": "RateLimitError"})
        result = get_platform_metrics()
        self.assertEqual(result["nodeSuccessRates"]["swot"], 50.0)
        self.assertEqual(result["latencyByNode"]["swot"], 2.0)

    def test_falls_back_to_process_counters_when_no_durable_runs_exist(self):
        from agent import metrics
        metrics.reset()
        metrics.increment("node.white_space.success")
        result = get_platform_metrics()
        self.assertEqual(result["nodeSuccessRates"]["white_space"], 100.0)

    def test_api_success_rate_uses_the_durable_log_and_agrees_with_failures(self):
        # Counters say "all fine" (a fresh process); the durable log says
        # 1 of 4 LLM-node runs failed. The headline must follow the log.
        from agent import metrics
        metrics.reset()
        metrics.increment("node.swot.success")
        for _ in range(3):
            events.record("node_latency", node="swot_analysis", detail={"seconds": 1.0})
        events.record("node_latency", node="mvp_recommendation", detail={"seconds": 1.0})
        events.record("pipeline_error", node="mvp", detail={"errorType": "NeedsDeepAnalysisError"})
        result = get_platform_metrics()
        self.assertEqual(result["kpis"]["apiSuccessRate"], 75.0)
        self.assertEqual(result["nodeSuccessRates"]["mvp"], 0.0)

    def test_deep_analysis_rate(self):
        events.record("cache_miss")
        events.record("cache_miss")
        events.record("pipeline_error", node="swot", detail={"errorType": "NeedsDeepAnalysisError"})
        result = get_platform_metrics()
        self.assertEqual(result["kpis"]["deepAnalysisRate"], 50.0)

    def test_model_usage_split(self):
        events.record("model_used", detail={"model": "groq/qwen/qwen3.8-27b", "elapsedMs": 100})
        events.record("model_used", detail={"model": "groq/qwen/qwen3.8-27b", "elapsedMs": 100})
        events.record("model_used", detail={"model": "gemini/gemini-3.6-flash", "elapsedMs": 100})
        result = get_platform_metrics()
        usage = {row["model"]: row["count"] for row in result["modelUsage"]}
        self.assertEqual(usage["groq/qwen/qwen3.8-27b"], 2)
        self.assertEqual(usage["gemini/gemini-3.6-flash"], 1)

    def test_token_usage_and_estimated_cost(self):
        events.record("cache_miss")
        events.record("model_used", detail={"model": "groq/qwen/qwen3.8-27b", "elapsedMs": 100, "promptTokens": 1_000_000, "completionTokens": 1_000_000, "totalTokens": 2_000_000})
        events.record("model_used", detail={"model": "groq/openai/gpt-oss-20b", "elapsedMs": 100, "promptTokens": 1000, "completionTokens": 0, "totalTokens": 1000})
        # An older event with no token fields counts as a call, not as tokens.
        events.record("model_used", detail={"model": "groq/qwen/qwen3.8-27b", "elapsedMs": 100})
        usage = get_platform_metrics(days=7)["tokenUsage"]
        self.assertEqual(usage["totalTokens"], 2_001_000)
        self.assertEqual(usage["promptTokens"], 1_001_000)
        self.assertEqual(usage["tokensTrackedCalls"], 2)
        self.assertEqual(usage["totalCalls"], 3)
        self.assertAlmostEqual(usage["estimatedCostUsd"], 0.29 + 0.59 + 0.00015, places=6)
        self.assertEqual(usage["avgTokensPerValidation"], 2_001_000)
        self.assertEqual(len(usage["daily"]), 7)
        self.assertEqual(usage["daily"][-1]["totalTokens"], 2_001_000)
        self.assertEqual(usage["byModel"][0]["model"], "groq/qwen/qwen3.8-27b")
        self.assertEqual(usage["byModel"][0]["calls"], 2)

    def test_token_usage_empty_window(self):
        usage = get_platform_metrics()["tokenUsage"]
        self.assertEqual(usage["totalTokens"], 0)
        self.assertIsNone(usage["avgCostPerValidationUsd"])

    def test_latency_by_node_averages_samples(self):
        events.record("node_latency", node="swot", detail={"seconds": 8.0})
        events.record("node_latency", node="swot", detail={"seconds": 10.0})
        result = get_platform_metrics()
        self.assertEqual(result["latencyByNode"]["swot"], 9.0)

    def test_top_categories(self):
        events.record("idea_category", detail={"category": "Fintech"})
        events.record("idea_category", detail={"category": "Fintech"})
        events.record("idea_category", detail={"category": "EdTech"})
        result = get_platform_metrics()
        top = result["topCategories"][0]
        self.assertEqual(top["category"], "Fintech")
        self.assertEqual(top["count"], 2)

    def test_email_delivery_summary(self):
        events.record("email_sent", detail={"outcome": "sent"})
        events.record("email_sent", detail={"outcome": "sent"})
        events.record("email_sent", detail={"outcome": "failed"})
        result = get_platform_metrics()
        self.assertEqual(result["emailDelivery"]["attempted"], 3)
        self.assertEqual(result["emailDelivery"]["sent"], 2)
        self.assertEqual(result["emailDelivery"]["failed"], 1)

    def test_recent_errors_use_configured_model_chain_not_a_single_model(self):
        events.record("pipeline_error", node="mvp", detail={"errorType": "ValueError"})
        result = get_platform_metrics()
        self.assertEqual(len(result["recentErrors"]), 1)
        self.assertIn("→", result["recentErrors"][0]["modelChain"])

    def test_no_data_does_not_crash(self):
        result = get_platform_metrics()
        self.assertEqual(result["kpis"]["totalValidations"], 0)
        self.assertEqual(result["kpis"]["cacheHitRate"], 0)
        self.assertIsNone(result["kpis"]["avgLatencySeconds"])


class AdminEndpointTests(unittest.TestCase):
    def setUp(self):
        _clear_users()
        events.clear()
        self.client = TestClient(main.app)

    def test_requires_auth(self):
        response = self.client.get("/admin/platform-metrics")
        self.assertEqual(response.status_code, 401)

    def test_non_admin_gets_403(self):
        signup_result = signup("founder@example.com", "correct-horse-battery")
        response = self.client.get(
            "/admin/platform-metrics", headers={"Authorization": f"Bearer {signup_result['token']}"}
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_gets_200_with_expected_shape(self):
        signup_result = signup("admin@example.com", "correct-horse-battery")
        _promote_to_admin(signup_result["user"]["id"])
        response = self.client.get(
            "/admin/platform-metrics", headers={"Authorization": f"Bearer {signup_result['token']}"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("kpis", body)
        self.assertIn("dailyVolume", body)
        self.assertIn("recentErrors", body)

    def test_auth_me_reports_is_admin(self):
        signup_result = signup("founder2@example.com", "correct-horse-battery")
        headers = {"Authorization": f"Bearer {signup_result['token']}"}

        before = self.client.get("/auth/me", headers=headers)
        self.assertFalse(before.json()["isAdmin"])

        _promote_to_admin(signup_result["user"]["id"])
        after = self.client.get("/auth/me", headers=headers)
        self.assertTrue(after.json()["isAdmin"])


if __name__ == "__main__":
    unittest.main()
