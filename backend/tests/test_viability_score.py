"""Tests for agent/viability_score.py - the Market Viability Score.

Standalone like test_milestone4_track_a.py: only imports viability_score.py
(and, transitively, opportunity_score.py), no fastapi/langgraph needed.
"""

import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.viability_score import calculate_market_viability

_STRONG_MARKET = {
    "marketSize": "The global market is worth billions and growing rapidly.",
    "trends": [
        {"text": "Rising demand", "sourceIds": ["src-1"]},
        {"text": "Growing adoption", "sourceIds": ["src-2"]},
        {"text": "Increasing investment", "sourceIds": []},
    ],
}

_WEAK_MARKET = {"marketSize": "", "trends": []}

_LOW_RISK_SWOT = {
    "risks": [
        {"risk": "Minor onboarding friction", "severity": "low", "likelihood": "low"},
    ]
}

_HIGH_RISK_SWOT = {
    "risks": [
        {"risk": "Regulatory exposure", "severity": "high", "likelihood": "high"},
        {"risk": "Thin margins", "severity": "high", "likelihood": "high"},
    ]
}


class MarketViabilityScoreTests(unittest.TestCase):
    def test_all_submetrics_and_score_are_bounded(self):
        result = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT)
        for key in ("score", "marketDemand", "executionRisk", "growthVelocity"):
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 100)

    def test_strong_market_with_low_risk_scores_higher_than_weak_market_with_high_risk(self):
        strong = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT)
        weak = calculate_market_viability(_WEAK_MARKET, _HIGH_RISK_SWOT)
        self.assertGreater(strong["score"], weak["score"])

    def test_high_severity_high_likelihood_risks_raise_execution_risk(self):
        low = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT)
        high = calculate_market_viability(_STRONG_MARKET, _HIGH_RISK_SWOT)
        self.assertLess(low["executionRisk"], high["executionRisk"])

    def test_no_risk_data_is_treated_as_uncertain_not_safe(self):
        # Missing risk data must not default to a perfect (0) risk score -
        # that would look like "no risk" instead of "unknown risk".
        result = calculate_market_viability(_STRONG_MARKET, None)
        self.assertGreater(result["executionRisk"], 0)

    def test_empty_market_and_swot_do_not_crash(self):
        result = calculate_market_viability({}, {})
        self.assertIsInstance(result["score"], int)

    def test_label_matches_score_tier(self):
        strong = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT)
        weak = calculate_market_viability(_WEAK_MARKET, _HIGH_RISK_SWOT)
        if strong["score"] >= 70:
            self.assertEqual(strong["label"], "Strong venture potential")
        if weak["score"] < 40:
            self.assertEqual(weak["label"], "Early signal")

    def test_growth_velocity_matches_growth_score_normalization(self):
        # growthVelocity is growth_score/30*100 - three trends each
        # matching a positive-growth signal (max growth_score=30) should
        # read as 100.
        max_growth_market = {
            "marketSize": "The global market is worth billions and growing rapidly.",
            "trends": [
                {"text": "Strong growth expected", "sourceIds": ["src-1"]},
                {"text": "Rising demand", "sourceIds": ["src-2"]},
                {"text": "Growing adoption", "sourceIds": []},
            ],
        }
        result = calculate_market_viability(max_growth_market, _LOW_RISK_SWOT)
        self.assertEqual(result["growthVelocity"], 100)


if __name__ == "__main__":
    unittest.main()
