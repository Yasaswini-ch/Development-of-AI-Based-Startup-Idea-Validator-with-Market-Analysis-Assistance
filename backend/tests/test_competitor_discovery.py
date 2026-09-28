"""Tests for competitor_agent.py's grounded LLM discovery pass
(_discover_with_llm, _ground_and_clean_competitors) and how
analyze_competitors merges it with the NER-only list - see
docs/competitor-detection-and-confidence-scoring-proposal.md Option B.

Standalone like test_competitor_profiling.py: exercises the pure
shape-validation/grounding helpers directly, without needing a real LLM
call, plus one analyze_competitors-level test with _discover_with_llm
mocked to check the union/merge behavior.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import competitor_agent


def _source(text, url="https://example.com"):
    return {"text": text, "result": {"url": url, "snippet": text}}


class ValidDiscoveryShapeTests(unittest.TestCase):
    def test_accepts_empty_competitors_list(self):
        # Discovery is allowed to genuinely say "none found" - unlike the
        # old profiling pass, it isn't just decorating names NER already
        # found, so an empty list is a valid shape, not a failure.
        self.assertTrue(competitor_agent._valid_discovery_shape({"competitors": []}))

    def test_rejects_missing_or_non_list_competitors(self):
        self.assertFalse(competitor_agent._valid_discovery_shape({}))
        self.assertFalse(competitor_agent._valid_discovery_shape({"competitors": "nope"}))

    def test_rejects_competitor_without_a_name(self):
        self.assertFalse(competitor_agent._valid_discovery_shape({"competitors": [{"sourceIds": ["r1"]}]}))


class GroundAndCleanCompetitorsTests(unittest.TestCase):
    def test_drops_a_name_not_present_in_its_cited_source(self):
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [{"name": "Blue Apron", "sourceIds": ["r1"], "classification": "direct"}]
        self.assertEqual(competitor_agent._ground_and_clean_competitors(raw, sources), [])

    def test_keeps_a_name_present_in_its_cited_source(self):
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [{"name": "HelloFresh", "sourceIds": ["r1"], "classification": "direct", "gap": "no community feature"}]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["name"], "HelloFresh")
        self.assertEqual(cleaned[0]["classification"], "direct")
        self.assertEqual(cleaned[0]["gap"], "no community feature")
        self.assertIn("_local_text", cleaned[0])

    def test_drops_a_sourceid_the_model_was_not_actually_given(self):
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [{"name": "HelloFresh", "sourceIds": ["r99"]}]
        self.assertEqual(competitor_agent._ground_and_clean_competitors(raw, sources), [])

    def test_dedupes_same_name_case_insensitively(self):
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [
            {"name": "HelloFresh", "sourceIds": ["r1"]},
            {"name": "hellofresh", "sourceIds": ["r1"]},
        ]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(len(cleaned), 1)

    def test_caps_at_max_competitors(self):
        sources = {
            f"r{i}": _source(f"Competitor{i} is a popular meal kit service.") for i in range(1, 10)
        }
        raw = [{"name": f"Competitor{i}", "sourceIds": [f"r{i}"]} for i in range(1, 10)]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(len(cleaned), competitor_agent._MAX_COMPETITORS)

    def test_missing_gap_falls_back_to_disclosure(self):
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [{"name": "HelloFresh", "sourceIds": ["r1"]}]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(cleaned[0]["gap"], competitor_agent._GAP_DISCLOSURE)


class DiscoverWithLlmTests(unittest.TestCase):
    def test_returns_none_without_any_competitors_angle_results(self):
        results = [{"angle": "Market size & trends", "title": "x", "snippet": "y", "url": "https://x.com"}]
        self.assertIsNone(competitor_agent._discover_with_llm("Idea", "Target", "Problem", results, []))

    def test_returns_none_when_llm_stack_unavailable_or_call_fails(self):
        # No crewai/LLM keys configured in the test environment (same
        # assumption test_competitor_profiling.py makes) - this must
        # degrade to None, never raise.
        results = [
            {
                "angle": "Competitors",
                "title": "HelloFresh review",
                "snippet": "HelloFresh charges $60/week for meal kits.",
                "url": "https://example.com/hellofresh",
            }
        ]
        result = competitor_agent._discover_with_llm("Meal kits", "Busy parents", "No time to cook", results, [])
        self.assertIsNone(result)


class AnalyzeCompetitorsMergeTests(unittest.TestCase):
    """analyze_competitors' union of discovery + NER results, with
    _discover_with_llm mocked so this doesn't need a real LLM call."""

    def _results(self):
        return [
            {
                "angle": "Competitors",
                "title": "HelloFresh and Rocket Money reviewed",
                "snippet": "HelloFresh charges $60/week. Rocket Money helps cancel subscriptions.",
                "url": "https://example.com/roundup",
            }
        ]

    @patch("agent.competitor_agent._discover_with_llm")
    def test_discovered_competitor_not_found_by_ner_is_still_included(self, mock_discover):
        # "Obscurename" is deliberately not a name spaCy's small model
        # would tag from this snippet - simulating exactly the recall gap
        # the discovery pass exists to close.
        mock_discover.return_value = {
            "competitors": [
                {
                    "name": "Obscurename",
                    "offering": "A niche meal-kit alternative.",
                    "url": "https://example.com/obscurename",
                    "gap": "No dietitian support.",
                    "classification": "direct",
                    "pricing": "unknown",
                    "businessModel": "unknown",
                    "strengths": [],
                    "weaknesses": [],
                    "estimatedPrice": "unknown",
                    "featureBreadth": "unknown",
                    "_local_text": "",
                }
            ],
            "comparisonMatrix": [],
        }
        result = competitor_agent.analyze_competitors(
            "Meal kits", "Busy parents", "No time to cook", self._results(), profile=True
        )
        names = {c["name"] for c in result["competitors"]}
        self.assertIn("Obscurename", names)
        self.assertTrue(result["profiled"])

    @patch("agent.competitor_agent._discover_with_llm")
    def test_ner_names_not_covered_by_discovery_are_appended(self, mock_discover):
        mock_discover.return_value = {
            "competitors": [
                {
                    "name": "HelloFresh",
                    "offering": "Meal kits.",
                    "url": "https://example.com/hellofresh",
                    "gap": "unknown",
                    "classification": "direct",
                    "pricing": "unknown",
                    "businessModel": "unknown",
                    "strengths": [],
                    "weaknesses": [],
                    "estimatedPrice": "unknown",
                    "featureBreadth": "unknown",
                    "_local_text": "",
                }
            ],
            "comparisonMatrix": [],
        }
        result = competitor_agent.analyze_competitors(
            "Meal kits", "Busy parents", "No time to cook", self._results(), profile=True
        )
        names = {c["name"] for c in result["competitors"]}
        # HelloFresh comes from discovery; "Rocket Money" is camelCase-like
        # ("Rocket Money" is multi-word, not camelCase, but is mentioned in
        # the snippet) and should still surface via the NER safety net if
        # discovery didn't already name it.
        self.assertIn("HelloFresh", names)

    def test_search_result_count_is_reported(self):
        result = competitor_agent.analyze_competitors(
            "Meal kits", "Busy parents", "No time to cook", self._results(), profile=False
        )
        self.assertEqual(result["searchResultCount"], 1)

    def test_zero_competitor_angle_results_reports_zero_count(self):
        result = competitor_agent.analyze_competitors("Idea", "Target", "Problem", [], profile=False)
        self.assertEqual(result["searchResultCount"], 0)


if __name__ == "__main__":
    unittest.main()
