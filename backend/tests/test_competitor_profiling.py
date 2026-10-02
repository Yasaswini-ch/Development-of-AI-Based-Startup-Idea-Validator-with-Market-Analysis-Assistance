"""Tests for competitor_agent.py's LLM profiling pass (_profile_with_llm)
and how analyze_competitors merges profiled fields onto the NER-only
competitor list, plus the comparison matrix sanitizer.

Standalone like test_competitor_gemini_refinement.py: exercises the pure
shape-validation/sanitization helpers directly, without needing a real
LLM call or the crewai/langgraph stack.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import competitor_agent


class ValidProfileShapeTests(unittest.TestCase):
    def test_accepts_only_known_names(self):
        data = {"profiles": {"Acme": {"classification": "direct"}}}
        self.assertTrue(competitor_agent._valid_profile_shape(data, {"Acme", "Beta"}))

    def test_rejects_unlisted_competitor_name(self):
        data = {"profiles": {"Invented Co": {"classification": "direct"}}}
        self.assertFalse(competitor_agent._valid_profile_shape(data, {"Acme"}))

    def test_rejects_empty_or_missing_profiles(self):
        self.assertFalse(competitor_agent._valid_profile_shape({"profiles": {}}, {"Acme"}))
        self.assertFalse(competitor_agent._valid_profile_shape({}, {"Acme"}))


class CleanProfileTests(unittest.TestCase):
    def test_invalid_classification_becomes_unknown(self):
        cleaned = competitor_agent._clean_profile({"classification": "sideways"})
        self.assertEqual(cleaned["classification"], "unknown")

    def test_missing_pricing_and_model_become_unknown(self):
        cleaned = competitor_agent._clean_profile({})
        self.assertEqual(cleaned["pricing"], "unknown")
        self.assertEqual(cleaned["businessModel"], "unknown")
        self.assertEqual(cleaned["strengths"], [])
        self.assertEqual(cleaned["weaknesses"], [])

    def test_lists_are_truncated_and_filtered(self):
        # _MAX_LIST_ITEMS raised 3 -> 5 (Sept 2026, richer-content pass) -
        # this input has 5 valid entries after filtering "" and the
        # non-string 5, so all 5 survive; a 6th would be the one actually
        # truncated.
        cleaned = competitor_agent._clean_profile(
            {"strengths": ["a", "", 5, "b", "c", "d", "e", "f"]}
        )
        self.assertEqual(cleaned["strengths"], ["a", "b", "c", "d", "e"])


class CleanMatrixTests(unittest.TestCase):
    def test_drops_rows_missing_required_fields(self):
        rows = [
            {"dimension": "Price", "idea": "Free tier", "competitors": {"Acme": "Paid only"}},
            {"dimension": "No idea cell", "competitors": {"Acme": "x"}},
            "not a dict",
        ]
        cleaned = competitor_agent._clean_matrix(rows, {"Acme"})
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["competitors"], {"Acme": "Paid only"})

    def test_drops_invented_competitor_columns(self):
        rows = [
            {
                "dimension": "Price",
                "idea": "Free tier",
                "competitors": {"Acme": "Paid only", "Invented Co": "??"},
            }
        ]
        cleaned = competitor_agent._clean_matrix(rows, {"Acme"})
        self.assertEqual(cleaned[0]["competitors"], {"Acme": "Paid only"})

    def test_non_list_input_returns_empty(self):
        self.assertEqual(competitor_agent._clean_matrix(None, {"Acme"}), [])


class AnalyzeCompetitorsProfilingTests(unittest.TestCase):
    def test_profile_false_skips_llm_call_entirely(self):
        results = [
            {
                "angle": "Competitors",
                "title": "HelloFresh review",
                "snippet": "HelloFresh charges $60/week for meal kits.",
                "url": "https://example.com/hellofresh",
            }
        ]
        result = competitor_agent.analyze_competitors("Meal kits", "Busy parents", "No time to cook", results)
        self.assertNotIn("profiled", result)
        self.assertNotIn("comparisonMatrix", result)

    def test_no_competitors_skips_profiling(self):
        result = competitor_agent.analyze_competitors("Idea", "Target", "Problem", [], profile=True)
        self.assertEqual(result["competitors"], [])
        self.assertNotIn("profiled", result)

    def test_profile_true_marks_unprofiled_on_llm_failure(self):
        # No crewai/LLM stack configured in this environment, and no real
        # competitors found from empty results either - either way,
        # _profile_with_llm returns None and analyze_competitors must not
        # raise or drop the base competitor list.
        results = [
            {
                "angle": "Competitors",
                "title": "HelloFresh review",
                "snippet": "HelloFresh charges $60/week for meal kits.",
                "url": "https://example.com/hellofresh",
            }
        ]
        if competitor_agent._nlp is None:
            self.skipTest("spaCy model not available in this environment")
        result = competitor_agent.analyze_competitors(
            "Meal kits", "Busy parents", "No time to cook", results, profile=True
        )
        if result["competitors"]:
            self.assertIn("profiled", result)


if __name__ == "__main__":
    unittest.main()
