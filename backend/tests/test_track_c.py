"""Milestone 4 / Track C - experiment_generator.py, action_plan.py, and
their graph wiring."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import unittest

from agent.action_plan import generate_action_plan
from agent.experiment_generator import generate_experiments
from agent.graph import action_plan_node, experiment_generator_node


_SWOT = {
    "risks": [
        {"risk": "Regulatory exposure could delay launch.", "severity": "high", "likelihood": "medium", "sourceIds": ["src-1"]},
        {"risk": "Thin margins at scale.", "severity": "medium", "likelihood": "low", "sourceIds": ["src-2"]},
        {"risk": "Minor UX friction in onboarding.", "severity": "low", "likelihood": "low", "sourceIds": []},
    ]
}
_MARKET = {
    "segments": [
        {
            "segment": "Busy families",
            "painPoints": "No time to cook",
            "motivations": "Convenience",
            "buyingBehavior": "Subscribes to recurring services",
            "sourceIds": ["src-3"],
        }
    ]
}
_MVP = {
    "features": [
        {"feature": "Landing page waitlist", "rationale": "Test demand", "impact": "high", "effort": "low", "sourceIds": ["src-1"]},
        {"feature": "Full checkout flow", "rationale": "Enable purchase", "impact": "high", "effort": "high", "sourceIds": []},
        {"feature": "Referral program", "rationale": "Grow organically", "impact": "medium", "effort": "medium", "sourceIds": []},
    ]
}
_GTM = {
    "positioning": "Convenient, affordable meal planning for busy families.",
    "positioningSourceIds": ["src-1"],
    "channels": [
        {"text": "Parenting Facebook groups", "sourceIds": ["src-2"]},
        {"text": "Local school newsletters", "sourceIds": []},
    ],
    "earlyCustomerApproach": "Recruit ten families for a pilot.",
    "earlyCustomerApproachSourceIds": [],
}


class GenerateExperimentsTests(unittest.TestCase):
    def test_generates_one_experiment_per_risk_in_severity_order(self):
        result = generate_experiments(_SWOT, _MARKET, _MVP)
        self.assertEqual(len(result), 3)
        # Highest severity (high) first, matching _SWOT's own risk order here.
        self.assertIn("Regulatory exposure", result[0]["hypothesis"].replace("regulatory exposure", "Regulatory exposure"))
        self.assertEqual(result[0]["relatedRiskIds"], ["risk-1"])
        self.assertEqual(result[1]["relatedRiskIds"], ["risk-2"])

    def test_every_experiment_has_the_full_contract_shape(self):
        result = generate_experiments(_SWOT, _MARKET, _MVP)
        for item in result:
            self.assertIsInstance(item["hypothesis"], str)
            self.assertIsInstance(item["method"], str)
            self.assertIsInstance(item["successMetric"], str)
            self.assertIsInstance(item["duration"], str)
            self.assertIn(item["budget"], {"low", "medium", "high", "unknown"})
            self.assertIsInstance(item["relatedRiskIds"], list)

    def test_uses_cheapest_feature_for_budget_and_duration(self):
        # The cheapest (lowest-effort) feature here is "Landing page
        # waitlist" (effort=low) -> budget=low, duration=7 days.
        result = generate_experiments(_SWOT, _MARKET, _MVP)
        self.assertEqual(result[0]["budget"], "low")
        self.assertEqual(result[0]["duration"], "7 days")

    def test_caps_at_max_experiments(self):
        many_risks = {
            "risks": [
                {"risk": f"Risk {i}", "severity": "high", "likelihood": "medium", "sourceIds": []}
                for i in range(10)
            ]
        }
        result = generate_experiments(many_risks, _MARKET, _MVP)
        self.assertLessEqual(len(result), 4)

    def test_no_risks_produces_no_experiments(self):
        self.assertEqual(generate_experiments({"risks": []}, _MARKET, _MVP), [])
        self.assertEqual(generate_experiments(None, _MARKET, _MVP), [])

    def test_handles_missing_market_and_mvp_without_crashing(self):
        result = generate_experiments(_SWOT, None, None)
        self.assertEqual(len(result), 3)
        for item in result:
            self.assertIsInstance(item["hypothesis"], str)


class GenerateActionPlanTests(unittest.TestCase):
    def test_returns_full_three_window_shape(self):
        result = generate_action_plan(_GTM, _MVP, _SWOT)
        self.assertEqual(set(result.keys()), {"next7Days", "next30Days", "next90Days"})
        for window in result.values():
            self.assertIsInstance(window["title"], str)
            self.assertIsInstance(window["items"], list)
            for item in window["items"]:
                self.assertIsInstance(item["text"], str)

    def test_next_7_days_prioritizes_highest_severity_risks(self):
        result = generate_action_plan(_GTM, _MVP, _SWOT)
        items_text = " ".join(item["text"] for item in result["next7Days"]["items"])
        self.assertIn("regulatory exposure", items_text.lower())

    def test_next_7_days_falls_back_to_features_with_no_risks(self):
        result = generate_action_plan(_GTM, _MVP, {"risks": []})
        items_text = " ".join(item["text"] for item in result["next7Days"]["items"])
        self.assertIn("landing page waitlist", items_text.lower())

    def test_next_30_days_prioritizes_high_impact_low_effort_features(self):
        result = generate_action_plan(_GTM, _MVP, _SWOT)
        items_text = " ".join(item["text"] for item in result["next30Days"]["items"])
        self.assertIn("landing page waitlist", items_text.lower())

    def test_next_90_days_uses_gtm_channels_in_order(self):
        result = generate_action_plan(_GTM, _MVP, _SWOT)
        self.assertIn("Parenting Facebook groups", result["next90Days"]["items"][0]["text"])

    def test_handles_all_none_sections_without_crashing(self):
        result = generate_action_plan(None, None, None)
        self.assertEqual(result["next7Days"]["items"], [])
        self.assertEqual(result["next30Days"]["items"], [])
        self.assertEqual(result["next90Days"]["items"], [])


class GraphNodeTests(unittest.TestCase):
    def test_experiment_generator_node_writes_experiments_into_state(self):
        state = {"swot": _SWOT, "marketOpportunity": _MARKET, "mvp": _MVP, "errors": {}}
        result = experiment_generator_node(state)
        self.assertIsInstance(result["experiments"], list)
        self.assertEqual(len(result["experiments"]), 3)

    def test_experiment_generator_node_skipped_on_pipeline_error(self):
        result = experiment_generator_node({"error": "search failed"})
        self.assertNotIn("experiments", result)

    def test_experiment_generator_node_failure_is_isolated(self):
        from unittest.mock import patch

        state = {"swot": None, "marketOpportunity": None, "mvp": None, "errors": {}}
        with patch("agent.graph.generate_experiments", side_effect=RuntimeError("failed")):
            result = experiment_generator_node(state)
        self.assertIsNone(result["experiments"])
        self.assertIn("experiments", result["errors"])

    def test_action_plan_node_writes_action_plan_into_state(self):
        state = {"gtm": _GTM, "mvp": _MVP, "swot": _SWOT, "errors": {}}
        result = action_plan_node(state)
        self.assertIn("next7Days", result["actionPlan"])

    def test_action_plan_node_skipped_on_pipeline_error(self):
        result = action_plan_node({"error": "search failed"})
        self.assertNotIn("actionPlan", result)

    def test_action_plan_node_failure_is_isolated(self):
        from unittest.mock import patch

        state = {"gtm": None, "mvp": None, "swot": None, "errors": {}}
        with patch("agent.graph.generate_action_plan", side_effect=RuntimeError("failed")):
            result = action_plan_node(state)
        self.assertIsNone(result["actionPlan"])
        self.assertIn("actionPlan", result["errors"])


if __name__ == "__main__":
    unittest.main()
