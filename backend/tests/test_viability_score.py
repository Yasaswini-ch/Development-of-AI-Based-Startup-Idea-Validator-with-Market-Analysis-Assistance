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

_CLEAR_COMPETITORS = {
    "competitors": [
        {"name": "Acme", "estimatedPrice": "mid", "featureBreadth": "broad"},
        {"name": "Beta Co", "estimatedPrice": "low", "featureBreadth": "narrow"},
    ]
}

_PARTIALLY_CLEAR_COMPETITORS = {
    "competitors": [
        {"name": "Acme", "estimatedPrice": "mid", "featureBreadth": "broad"},
        {"name": "Beta Co", "estimatedPrice": "unknown", "featureBreadth": "unknown"},
    ]
}

_FRESH_SOURCES = {"sourcesWithKnownDate": 3, "totalSources": 3, "medianAgeDays": 2}
_STALE_SOURCES = {"sourcesWithKnownDate": 3, "totalSources": 3, "medianAgeDays": 900}


class MarketViabilityScoreTests(unittest.TestCase):
    def test_all_submetrics_and_score_are_bounded(self):
        result = calculate_market_viability(
            _STRONG_MARKET, _LOW_RISK_SWOT, _CLEAR_COMPETITORS, _FRESH_SOURCES
        )
        for key in ("score", "marketDemand", "executionRisk", "growthVelocity", "competitionClarity", "timing"):
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

    def test_competitors_and_source_recency_are_optional_and_do_not_affect_headline_score(self):
        # competitionClarity/timing are informational, not part of `score`
        # (see the module docstring) - the headline number must be
        # identical whether or not these optional args are passed.
        without = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT)
        with_data = calculate_market_viability(
            _STRONG_MARKET, _LOW_RISK_SWOT, _CLEAR_COMPETITORS, _FRESH_SOURCES
        )
        self.assertEqual(without["score"], with_data["score"])
        self.assertIn("competitionClarity", without)
        self.assertIn("timing", without)

    def test_no_competitors_found_is_uncertain_not_zero_or_perfect(self):
        # Zero competitors found is genuinely ambiguous (blue ocean vs.
        # thin search coverage), so it must not read as either "fully
        # clear" or "fully unclear."
        none_found = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, {"competitors": []})
        self.assertGreater(none_found["competitionClarity"], 0)
        self.assertLess(none_found["competitionClarity"], 100)

    def test_partial_clarity_scores_between_none_and_fully_unclear(self):
        partial = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, _PARTIALLY_CLEAR_COMPETITORS)
        clear = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, _CLEAR_COMPETITORS)
        self.assertGreater(partial["competitionClarity"], 0)
        self.assertLess(partial["competitionClarity"], clear["competitionClarity"])

    def test_fully_clear_competitor_data_scores_100(self):
        result = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, _CLEAR_COMPETITORS)
        self.assertEqual(result["competitionClarity"], 100)

    def test_fresh_sources_score_higher_timing_than_stale_sources(self):
        fresh = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, None, _FRESH_SOURCES)
        stale = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, None, _STALE_SOURCES)
        self.assertGreater(fresh["timing"], stale["timing"])

    def test_missing_median_age_is_treated_as_uncertain_not_stale(self):
        no_dates = calculate_market_viability(
            _STRONG_MARKET, _LOW_RISK_SWOT, None, {"sourcesWithKnownDate": 0, "totalSources": 3, "medianAgeDays": None}
        )
        stale = calculate_market_viability(_STRONG_MARKET, _LOW_RISK_SWOT, None, _STALE_SOURCES)
        self.assertGreater(no_dates["timing"], stale["timing"])


if __name__ == "__main__":
    unittest.main()
