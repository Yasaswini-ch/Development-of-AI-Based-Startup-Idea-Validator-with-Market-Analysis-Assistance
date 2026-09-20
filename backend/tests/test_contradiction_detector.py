"""Milestone 4 / Track B - contradiction_detector.py and its graph wiring."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import unittest

from agent.contradiction_detector import detect_contradictions
from agent.graph import contradiction_detector_node


_GROWING_MARKET = {
    "marketSize": "The market is growing rapidly.",
    "trends": [{"text": "Rising demand for the category", "sourceIds": ["src-1"]}],
    "segments": [
        {
            "segment": "Budget-conscious families",
            "painPoints": "Existing options are too expensive.",
            "motivations": "Value for money.",
            "buyingBehavior": "Not clear from the sources.",
            "sourceIds": ["src-2"],
        }
    ],
}


class MarketGrowthVsWeakDemandTests(unittest.TestCase):
    def test_flags_growing_market_with_weak_demand_segment(self):
        result = detect_contradictions(_GROWING_MARKET, None, None, None)
        types = [c["type"] for c in result]
        self.assertIn("marketGrowthVsWeakDemand", types)
        flag = next(c for c in result if c["type"] == "marketGrowthVsWeakDemand")
        self.assertIn("src-1", flag["sourceIds"])
        self.assertIn("src-2", flag["sourceIds"])

    def test_no_flag_without_growth_signal(self):
        market = {
            "marketSize": "The market is small and stable.",
            "trends": [],
            "segments": _GROWING_MARKET["segments"],
        }
        result = detect_contradictions(market, None, None, None)
        self.assertNotIn("marketGrowthVsWeakDemand", [c["type"] for c in result])

    def test_no_flag_without_weak_demand_segment(self):
        market = {
            "marketSize": "The market is growing rapidly.",
            "trends": [],
            "segments": [
                {
                    "segment": "Early adopters",
                    "painPoints": "p",
                    "motivations": "m",
                    "buyingBehavior": "Actively searching and purchasing today.",
                    "sourceIds": [],
                }
            ],
        }
        result = detect_contradictions(market, None, None, None)
        self.assertNotIn("marketGrowthVsWeakDemand", [c["type"] for c in result])


class HighOpportunityVsHighSeverityRisksTests(unittest.TestCase):
    def test_flags_high_score_with_multiple_high_severity_risks(self):
        market = {"opportunityScore": 85}
        swot = {
            "risks": [
                {"risk": "Regulatory exposure", "severity": "high", "likelihood": "medium", "sourceIds": ["src-1"]},
                {"risk": "Thin margins", "severity": "high", "likelihood": "low", "sourceIds": ["src-2"]},
                {"risk": "Minor UX gap", "severity": "low", "likelihood": "low", "sourceIds": []},
            ]
        }
        result = detect_contradictions(market, swot, None, None)
        flag = next(c for c in result if c["type"] == "highOpportunityVsHighSeverityRisks")
        self.assertIn("src-1", flag["sourceIds"])
        self.assertIn("src-2", flag["sourceIds"])

    def test_no_flag_below_score_threshold(self):
        market = {"opportunityScore": 50}
        swot = {
            "risks": [
                {"risk": "A", "severity": "high", "likelihood": "medium", "sourceIds": []},
                {"risk": "B", "severity": "high", "likelihood": "medium", "sourceIds": []},
            ]
        }
        result = detect_contradictions(market, swot, None, None)
        self.assertNotIn("highOpportunityVsHighSeverityRisks", [c["type"] for c in result])

    def test_no_flag_with_only_one_high_severity_risk(self):
        market = {"opportunityScore": 90}
        swot = {"risks": [{"risk": "A", "severity": "high", "likelihood": "medium", "sourceIds": []}]}
        result = detect_contradictions(market, swot, None, None)
        self.assertNotIn("highOpportunityVsHighSeverityRisks", [c["type"] for c in result])


class PremiumPositioningVsPriceSensitiveSegmentTests(unittest.TestCase):
    def test_flags_premium_positioning_with_price_sensitive_segment(self):
        gtm = {"positioning": "A premium, high-end offering for discerning buyers.", "positioningSourceIds": ["src-1"]}
        market = {
            "segments": [
                {
                    "segment": "Budget shoppers",
                    "painPoints": "Cost is the main barrier.",
                    "motivations": "Finding the cheapest option.",
                    "buyingBehavior": "Highly price-sensitive.",
                    "sourceIds": ["src-2"],
                }
            ]
        }
        result = detect_contradictions(market, None, None, gtm)
        flag = next(c for c in result if c["type"] == "premiumPositioningVsPriceSensitiveSegment")
        self.assertIn("src-1", flag["sourceIds"])
        self.assertIn("src-2", flag["sourceIds"])

    def test_no_flag_without_premium_positioning(self):
        gtm = {"positioning": "A practical, everyday tool for busy teams.", "positioningSourceIds": []}
        result = detect_contradictions(_GROWING_MARKET, None, None, gtm)
        self.assertNotIn("premiumPositioningVsPriceSensitiveSegment", [c["type"] for c in result])


class BroadMvpScopeVsHighEffortLimitedValidationTests(unittest.TestCase):
    def test_flags_broad_high_effort_unvalidated_scope(self):
        mvp = {
            "features": [
                {"feature": "A", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": []},
                {"feature": "B", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": []},
                {"feature": "C", "rationale": "r", "impact": "medium", "effort": "high", "sourceIds": ["src-1"]},
                {"feature": "D", "rationale": "r", "impact": "low", "effort": "low", "sourceIds": ["src-2"]},
            ]
        }
        result = detect_contradictions(None, None, mvp, None)
        flag = next(c for c in result if c["type"] == "broadMvpScopeVsHighEffortLimitedValidation")
        self.assertIn("src-1", flag["sourceIds"])
        self.assertIn("src-2", flag["sourceIds"])

    def test_no_flag_with_too_few_features(self):
        mvp = {
            "features": [
                {"feature": "A", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": []},
                {"feature": "B", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": []},
            ]
        }
        result = detect_contradictions(None, None, mvp, None)
        self.assertNotIn("broadMvpScopeVsHighEffortLimitedValidation", [c["type"] for c in result])

    def test_no_flag_when_features_are_well_validated(self):
        mvp = {
            "features": [
                {"feature": "A", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": ["src-1"]},
                {"feature": "B", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": ["src-2"]},
                {"feature": "C", "rationale": "r", "impact": "medium", "effort": "low", "sourceIds": ["src-1"]},
                {"feature": "D", "rationale": "r", "impact": "low", "effort": "low", "sourceIds": ["src-2"]},
            ]
        }
        result = detect_contradictions(None, None, mvp, None)
        self.assertNotIn("broadMvpScopeVsHighEffortLimitedValidation", [c["type"] for c in result])


class DetectContradictionsTests(unittest.TestCase):
    def test_handles_all_none_sections_without_crashing(self):
        self.assertEqual(detect_contradictions(None, None, None, None), [])

    def test_caps_at_max_contradictions(self):
        # Only 4 checks exist today, so this just confirms the cap doesn't
        # truncate a normal, fully-triggered result.
        mvp = {
            "features": [
                {"feature": "A", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": []},
                {"feature": "B", "rationale": "r", "impact": "high", "effort": "high", "sourceIds": []},
                {"feature": "C", "rationale": "r", "impact": "medium", "effort": "high", "sourceIds": []},
                {"feature": "D", "rationale": "r", "impact": "low", "effort": "high", "sourceIds": []},
            ]
        }
        swot = {
            "risks": [
                {"risk": "A", "severity": "high", "likelihood": "medium", "sourceIds": []},
                {"risk": "B", "severity": "high", "likelihood": "medium", "sourceIds": []},
            ]
        }
        gtm = {"positioning": "A premium offering.", "positioningSourceIds": []}
        market = {
            **_GROWING_MARKET,
            "opportunityScore": 90,
            "segments": [
                {
                    **_GROWING_MARKET["segments"][0],
                    "motivations": "Value for money, but demand is not clear from the sources.",
                    "buyingBehavior": "Highly price-sensitive and budget-conscious.",
                }
            ],
        }
        result = detect_contradictions(market, swot, mvp, gtm)
        self.assertEqual(len(result), 4)


class ContradictionDetectorNodeTests(unittest.TestCase):
    def test_node_writes_contradictions_into_state(self):
        state = {
            "marketOpportunity": _GROWING_MARKET,
            "swot": None,
            "mvp": None,
            "gtm": None,
            "errors": {},
        }
        result = contradiction_detector_node(state)
        self.assertIsInstance(result["contradictions"], list)
        self.assertTrue(len(result["contradictions"]) >= 1)

    def test_node_skipped_on_pipeline_error(self):
        state = {"error": "search failed"}
        result = contradiction_detector_node(state)
        self.assertNotIn("contradictions", result)

    def test_node_failure_is_isolated_like_other_nodes(self):
        state = {
            "marketOpportunity": None,
            "swot": None,
            "mvp": None,
            "gtm": None,
            "errors": {},
        }
        from unittest.mock import patch

        with patch("agent.graph.detect_contradictions", side_effect=RuntimeError("failed")):
            result = contradiction_detector_node(state)
        self.assertIsNone(result["contradictions"])
        self.assertIn("contradictions", result["errors"])


if __name__ == "__main__":
    unittest.main()
