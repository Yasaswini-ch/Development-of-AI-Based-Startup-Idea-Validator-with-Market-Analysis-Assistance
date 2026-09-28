"""Tests for opportunity_score.py's competition-density scoring fix - see
docs/competitor-detection-and-confidence-scoring-proposal.md §2.2 and §4.
Zero found competitors no longer scores a perfect 30/30 unconditionally,
and a classified "indirect" competitor counts for half a "direct" one.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.opportunity_score import _competition_score, calculate_opportunity_score

_STRONG_MARKET = {
    "marketSize": "The global market is worth billions and growing.",
    "trends": ["Rising adoption", "Demand is growing", "Expanding use cases"],
}


class CompetitionScoreTests(unittest.TestCase):
    def test_zero_competitors_with_thin_search_data_is_neutral_not_max(self):
        # Fewer than _MIN_SEARCH_RESULTS_FOR_CONFIDENT_ZERO Competitors-
        # angle results means "we barely looked", not "we looked and found
        # nothing" - this must not score as a perfect open market.
        score = _competition_score({"competitors": [], "searchResultCount": 1})
        self.assertEqual(score, 15)

    def test_zero_competitors_with_solid_search_coverage_scores_max(self):
        score = _competition_score({"competitors": [], "searchResultCount": 5})
        self.assertEqual(score, 30)

    def test_missing_search_result_count_defaults_to_neutral(self):
        # Callers (e.g. cached older results) that never set
        # searchResultCount must not silently get the old max-points
        # behavior back.
        score = _competition_score({"competitors": []})
        self.assertEqual(score, 15)

    def test_unclassified_competitors_score_same_as_before(self):
        # No "classification" field (NER-only / quick mode) means full
        # weight per competitor, matching the old count-only scoring.
        self.assertEqual(_competition_score({"competitors": [{"name": "One"}, {"name": "Two"}]}), 18)

    def test_indirect_competitor_counts_for_half(self):
        score_two_direct = _competition_score(
            {"competitors": [{"name": "One", "classification": "direct"}, {"name": "Two", "classification": "direct"}]}
        )
        score_one_direct_one_indirect = _competition_score(
            {
                "competitors": [
                    {"name": "One", "classification": "direct"},
                    {"name": "Two", "classification": "indirect"},
                ]
            }
        )
        self.assertGreater(score_one_direct_one_indirect, score_two_direct)

    def test_four_direct_competitors_scores_lowest_bucket(self):
        competitors = [{"name": str(i), "classification": "direct"} for i in range(4)]
        self.assertEqual(_competition_score({"competitors": competitors}), 6)

    def test_backward_compatible_with_plain_competitor_list_shape(self):
        # calculate_opportunity_score passes the whole competitor_data
        # dict through now, but existing callers that hand it
        # {"competitors": [...]} with no searchResultCount must keep
        # working - only the zero-competitor case changes.
        score = calculate_opportunity_score(
            _STRONG_MARKET,
            {"competitors": [{"name": "One"}, {"name": "Two"}]},
            [],
        )
        self.assertGreaterEqual(score, 80)


if __name__ == "__main__":
    unittest.main()
