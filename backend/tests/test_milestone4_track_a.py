"""Milestone 4 / Track A - focused tests for sourceIds in market_agent.py
and the shared structured_output.py validation helpers.

Split out from test_milestone2.py/test_milestone3.py (which need fastapi/
langgraph, unavailable in some environments) so these pure-logic checks -
which need only market_agent.py, structured_output.py, and
deterministic_fallback.py - can run standalone.
"""

import unittest
from pathlib import Path
from unittest.mock import patch
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import market_agent
from agent import swot_agent
from agent.deterministic_fallback import deterministic_market_opportunity
from agent.opportunity_score import calculate_opportunity_score
from agent.structured_output import compact_sources, sanitize_source_ids, valid_source_ids

_RESULTS = [
    {
        "title": "Market report: category is booming",
        "snippet": "The category is growing fast, with rising demand.",
        "url": "https://example.com/market-report",
        "angle": "Market size & trends",
        "score": 0.9,
    },
    {
        "title": "Top competitors overview",
        "snippet": "Several players already compete here.",
        "url": "https://example.com/competitors",
        "angle": "Competitors",
        "score": 0.5,
    },
]

_VALID_TRENDS = [{"text": "Rising demand for the category", "sourceIds": ["src-1"]}]
_VALID_SEGMENTS = [
    {
        "segment": "Urban millennials",
        "painPoints": "Limited time to compare options",
        "motivations": "Convenience",
        "buyingBehavior": "Research online",
        "sourceIds": ["src-2"],
    }
]


class SharedValidatorHelpersTests(unittest.TestCase):
    """structured_output.py's new shared sourceIds helpers."""

    def test_valid_source_ids_accepts_list_of_strings(self):
        self.assertTrue(valid_source_ids([]))
        self.assertTrue(valid_source_ids(["src-1", "src-2"]))

    def test_valid_source_ids_rejects_wrong_types(self):
        self.assertFalse(valid_source_ids("src-1"))  # B: bare string, not a list
        self.assertFalse(valid_source_ids(["src-1", 2]))  # B: non-string item
        self.assertFalse(valid_source_ids(None))

    def test_sanitize_source_ids_drops_unknown_and_dedupes(self):
        valid_ids = {"src-1", "src-2"}
        # C: a sourceId the model invented (src-99) that isn't in the
        # available sources must be dropped, not passed through.
        result = sanitize_source_ids(["src-1", "src-99", "src-1", "src-2"], valid_ids)
        self.assertEqual(result, ["src-1", "src-2"])

    def test_sanitize_source_ids_handles_non_list_input(self):
        self.assertEqual(sanitize_source_ids("not-a-list", {"src-1"}), [])
        self.assertEqual(sanitize_source_ids(None, {"src-1"}), [])


class MarketAgentShapeValidationTests(unittest.TestCase):
    """market_agent.py's _is_valid_shape / _is_valid_trend / _is_valid_segment."""

    def test_valid_output_with_valid_source_ids_is_accepted(self):
        # A: a well-formed Market Agent output with sourceIds passes.
        data = {
            "marketSize": "The global market is worth billions and growing.",
            "trends": _VALID_TRENDS,
            "segments": _VALID_SEGMENTS,
        }
        self.assertTrue(market_agent._is_valid_shape(data))

    def test_trend_with_non_list_source_ids_is_rejected(self):
        # B: sourceIds must be a list of strings, not a bare string.
        data = {
            "marketSize": "text",
            "trends": [{"text": "A trend", "sourceIds": "src-1"}],
            "segments": _VALID_SEGMENTS,
        }
        self.assertFalse(market_agent._is_valid_shape(data))

    def test_segment_with_non_string_source_id_is_rejected(self):
        # B: every sourceId must itself be a string.
        bad_segment = {**_VALID_SEGMENTS[0], "sourceIds": [123]}
        data = {
            "marketSize": "text",
            "trends": _VALID_TRENDS,
            "segments": [bad_segment],
        }
        self.assertFalse(market_agent._is_valid_shape(data))

    def test_trend_missing_source_ids_key_defaults_to_valid(self):
        # sourceIds may be omitted by a non-compliant model response - the
        # validator treats a missing key the same as an empty list (same
        # leniency swot_agent.py's _valid_claim_list applies), it isn't
        # required to be present to pass shape validation.
        data = {
            "marketSize": "text",
            "trends": [{"text": "A trend"}],
            "segments": _VALID_SEGMENTS,
        }
        self.assertTrue(market_agent._is_valid_shape(data))

    def test_bare_string_trend_is_rejected(self):
        # D: the OLD shape (plain string trends) must now be rejected -
        # this is the intentional, documented contract change; existing
        # segment-shape validation (segment/painPoints/motivations/
        # buyingBehavior all required strings) is unchanged and still works.
        data = {
            "marketSize": "text",
            "trends": ["A trend as a bare string"],
            "segments": _VALID_SEGMENTS,
        }
        self.assertFalse(market_agent._is_valid_shape(data))

    def test_existing_segment_required_fields_still_enforced(self):
        # D: segment validation for the four original fields is unchanged.
        incomplete_segment = {"segment": "X", "painPoints": "p", "sourceIds": []}
        data = {"marketSize": "text", "trends": _VALID_TRENDS, "segments": [incomplete_segment]}
        self.assertFalse(market_agent._is_valid_shape(data))


class BuildContextTests(unittest.TestCase):
    def test_source_id_is_shown_alongside_its_evidence(self):
        # G: a search result's sourceId is actually available to the LLM
        # context, tagged directly next to the evidence it belongs to.
        context, sources = market_agent._build_context(_RESULTS)
        self.assertIn("[src-1]", context)
        self.assertIn("Market report: category is booming", context)
        self.assertEqual(sources[0]["sourceId"], "src-1")

    def test_source_ids_match_compact_sources_canonical_numbering(self):
        # Critical correctness check: market_agent's own sourceId numbering
        # must match compact_sources(results) on the plain, un-reordered
        # results list - the same convention swot_agent.py and graph.py's
        # confidence dashboard use - even though _build_context re-sorts
        # for DISPLAY (market-angle sources first).
        _, sources = market_agent._build_context(_RESULTS)
        canonical = compact_sources(_RESULTS, limit=len(_RESULTS))
        by_id = {s["sourceId"]: s for s in sources}
        for expected in canonical:
            self.assertEqual(by_id[expected["sourceId"]]["url"], expected["url"])

    def test_empty_results_produce_no_sources(self):
        context, sources = market_agent._build_context([])
        self.assertEqual(sources, [])
        self.assertIn("No search results", context)


class DeterministicFallbackTests(unittest.TestCase):
    def test_fallback_does_not_crash_and_has_source_ids(self):
        # F: the deterministic fallback must not crash, and must return the
        # same {"text"/"segment", ..., "sourceIds"} contract as the real path.
        result = deterministic_market_opportunity("An idea", "Target customer", "A problem", _RESULTS)
        self.assertTrue(result["degraded"])
        self.assertTrue(all(isinstance(t, dict) and "sourceIds" in t for t in result["trends"]))
        self.assertTrue(all("sourceIds" in s for s in result["segments"]))

    def test_fallback_trend_cites_the_real_matching_source(self):
        # A fallback trend derived from a specific result's title/url must
        # cite that same result's sourceId, not a guess.
        result = deterministic_market_opportunity("An idea", "Target customer", "A problem", _RESULTS)
        trend_texts = {t["text"]: t["sourceIds"] for t in result["trends"]}
        self.assertIn("Market report: category is booming", trend_texts)
        self.assertEqual(trend_texts["Market report: category is booming"], ["src-1"])

    @patch("agent.market_agent.kickoff_with_fallback")
    def test_analyze_market_opportunity_falls_back_safely(self, mock_kickoff):
        # F: analyze_market_opportunity itself must not crash when the LLM
        # call fails (mocked here to always raise, the same as a real
        # rate-limit/no-API-key failure would) - it should transparently
        # return the deterministic fallback instead. Mocked rather than
        # relying on the ambient test environment lacking an API key, since
        # a real GROQ_API_KEY present at test time would otherwise make
        # this call out to the live Groq API - slow, network-dependent, and
        # liable to fail this assertion outright if the real call succeeds.
        mock_kickoff.side_effect = RuntimeError("LLM call failed")
        result = market_agent.analyze_market_opportunity("An idea", "Target customer", "A problem", _RESULTS)
        mock_kickoff.assert_called_once()
        self.assertTrue(result.get("degraded"))
        self.assertTrue(all(isinstance(t, dict) and "sourceIds" in t for t in result["trends"]))


class OpportunityScoreCompatibilityTests(unittest.TestCase):
    def test_growth_score_handles_new_claim_object_trends(self):
        # Compatibility fix: trends are now {"text","sourceIds"} objects -
        # scoring must still work.
        score_objects = calculate_opportunity_score(
            {
                "marketSize": "The global market is worth billions and growing.",
                "trends": [
                    {"text": "Rising adoption", "sourceIds": ["src-1"]},
                    {"text": "Demand is growing", "sourceIds": []},
                    {"text": "Expanding use cases", "sourceIds": ["src-2"]},
                ],
            },
            {"competitors": [{"name": "One"}, {"name": "Two"}]},
            [],
        )
        # E/D: identical inputs (same text, old shape) must still score the
        # same - existing behavior is preserved, not just "still runs".
        score_strings = calculate_opportunity_score(
            {
                "marketSize": "The global market is worth billions and growing.",
                "trends": ["Rising adoption", "Demand is growing", "Expanding use cases"],
            },
            {"competitors": [{"name": "One"}, {"name": "Two"}]},
            [],
        )
        self.assertEqual(score_objects, score_strings)
        self.assertGreaterEqual(score_objects, 80)


class SwotAgentSmokeTest(unittest.TestCase):
    """E: swot_agent.py's own (untouched) validation still works - swot_agent.py
    was not modified by this Track A change, this just confirms importing/
    calling it is unaffected by the new structured_output.py additions
    (which are purely additive - swot_agent.py's own imports are untouched).
    """

    def test_swot_valid_shape_unaffected(self):
        data = {
            "strengths": [{"text": "Focused niche", "sourceIds": ["src-1"]}],
            "weaknesses": [{"text": "Limited proof", "sourceIds": []}],
            "opportunities": [{"text": "Growing demand", "sourceIds": ["src-1"]}],
            "threats": [{"text": "Established rivals", "sourceIds": []}],
            "risks": [
                {"risk": "Low adoption", "severity": "high", "likelihood": "medium", "sourceIds": ["src-1"]}
            ],
        }
        self.assertTrue(swot_agent._valid_shape(data))


if __name__ == "__main__":
    unittest.main()
