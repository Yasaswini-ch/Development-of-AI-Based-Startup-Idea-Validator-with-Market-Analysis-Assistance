"""Tests for competitor_agent.py's best-effort external enrichment
(_producthunt_lookup, _wikidata_lookup, _enrich_with_apis) - previously
untested, which is how a Product Hunt query that declared a GraphQL
variable ($name) but never referenced it anywhere in the query body went
unnoticed: every spec-compliant GraphQL server rejects that as a
validation error ("All Variables Used" - spec.graphql.org/draft/#sec-All-
Variables-Used), so the original query failed on every single call,
silently swallowed by the broad except and indistinguishable from "no
match found." Fixed by dropping the unused variable; these tests lock in
both the fix (no `variables` sent) and the lookup functions' existing
best-effort contract (never raise, "unknown" stays "unknown" rather than
a guess).
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import competitor_agent


def _fake_response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class ProductHuntLookupTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"PRODUCTHUNT_API_TOKEN": "test-token"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_none_without_a_token_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(competitor_agent._producthunt_lookup("HelloFresh"))

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_sends_no_variables_regression_for_the_unused_dollar_name_bug(self, mock_urlopen):
        # The bug: an earlier version declared `query($name: String!)` but
        # never referenced $name in the query body, which the GraphQL spec
        # requires every server to reject outright - "variables" should
        # never be sent at all now that the query takes none.
        mock_urlopen.return_value = _fake_response({"data": {"posts": {"edges": []}}})
        competitor_agent._producthunt_lookup("HelloFresh")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data)
        self.assertNotIn("variables", body)
        self.assertNotIn("$name", body["query"])

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_enrichment_when_a_post_name_matches(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {
                "data": {
                    "posts": {
                        "edges": [
                            {
                                "node": {
                                    "name": "HelloFresh",
                                    "tagline": "Meal kits delivered weekly",
                                    "votesCount": 1200,
                                    "website": "https://hellofresh.com",
                                    "url": "https://producthunt.com/posts/hellofresh",
                                }
                            }
                        ]
                    }
                }
            }
        )
        result = competitor_agent._producthunt_lookup("HelloFresh")
        self.assertEqual(result["source"], "producthunt")
        self.assertEqual(result["tagline"], "Meal kits delivered weekly")
        self.assertEqual(result["votesCount"], 1200)

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_matches_case_insensitively(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"data": {"posts": {"edges": [{"node": {"name": "hellofresh", "tagline": "x"}}]}}}
        )
        result = competitor_agent._producthunt_lookup("HelloFresh")
        self.assertIsNotNone(result)

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_none_when_no_post_name_matches(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"data": {"posts": {"edges": [{"node": {"name": "SomeOtherApp"}}]}}}
        )
        self.assertIsNone(competitor_agent._producthunt_lookup("HelloFresh"))

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_none_and_does_not_raise_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("boom")
        self.assertIsNone(competitor_agent._producthunt_lookup("HelloFresh"))

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_none_and_does_not_raise_on_a_graphql_error_response(self, mock_urlopen):
        # A validation error (like the original $name bug) comes back as
        # an "errors" body with no "data" key - must degrade to None, not
        # raise a KeyError.
        mock_urlopen.return_value = _fake_response(
            {"errors": [{"message": "Variable \"$name\" is never used in operation"}]}
        )
        self.assertIsNone(competitor_agent._producthunt_lookup("HelloFresh"))


class WikidataLookupTests(unittest.TestCase):
    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_none_on_no_hits(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"search": []})
        self.assertIsNone(competitor_agent._wikidata_lookup("HelloFresh"))

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_none_on_a_loose_or_partial_label_match(self, mock_urlopen):
        # A hit whose own label isn't the exact name is more likely a
        # false match (a person, an unrelated org) than the real company.
        mock_urlopen.return_value = _fake_response(
            {"search": [{"id": "Q1", "label": "HelloFresh Group", "description": "a company"}]}
        )
        self.assertIsNone(competitor_agent._wikidata_lookup("HelloFresh"))

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_enrichment_with_founding_year_on_exact_match(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {
                "search": [
                    {
                        "id": "Q19883233",
                        "label": "HelloFresh",
                        "description": "German meal-kit company founded in 2011",
                    }
                ]
            }
        )
        result = competitor_agent._wikidata_lookup("HelloFresh")
        self.assertEqual(result["source"], "wikidata")
        self.assertEqual(result["foundedYear"], 2011)
        self.assertIn("Q19883233", result["url"])

    @patch("agent.competitor_agent.urllib.request.urlopen")
    def test_returns_none_and_does_not_raise_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("boom")
        self.assertIsNone(competitor_agent._wikidata_lookup("HelloFresh"))


class EnrichWithApisTests(unittest.TestCase):
    def _competitor(self, name):
        return {"name": name, "offering": "x", "url": "https://x.com", "gap": "unknown"}

    @patch("agent.competitor_agent._wikidata_lookup")
    @patch("agent.competitor_agent._producthunt_lookup")
    def test_prefers_producthunt_over_wikidata_when_both_match(self, mock_ph, mock_wd):
        mock_ph.return_value = {"source": "producthunt"}
        mock_wd.return_value = {"source": "wikidata"}
        competitors = [self._competitor("HelloFresh")]
        competitor_agent._enrich_with_apis(competitors)
        self.assertEqual(competitors[0]["enrichment"]["source"], "producthunt")
        mock_wd.assert_not_called()

    @patch("agent.competitor_agent._wikidata_lookup")
    @patch("agent.competitor_agent._producthunt_lookup")
    def test_falls_back_to_wikidata_when_producthunt_has_no_match(self, mock_ph, mock_wd):
        mock_ph.return_value = None
        mock_wd.return_value = {"source": "wikidata"}
        competitors = [self._competitor("HelloFresh")]
        competitor_agent._enrich_with_apis(competitors)
        self.assertEqual(competitors[0]["enrichment"]["source"], "wikidata")

    @patch("agent.competitor_agent._wikidata_lookup", return_value=None)
    @patch("agent.competitor_agent._producthunt_lookup", return_value=None)
    def test_no_enrichment_key_added_when_neither_source_matches(self, mock_ph, mock_wd):
        competitors = [self._competitor("HelloFresh")]
        competitor_agent._enrich_with_apis(competitors)
        self.assertNotIn("enrichment", competitors[0])

    @patch("agent.competitor_agent._wikidata_lookup", return_value=None)
    @patch("agent.competitor_agent._producthunt_lookup", return_value={"source": "producthunt"})
    def test_only_enriches_up_to_max_enriched_competitors(self, mock_ph, mock_wd):
        competitors = [self._competitor(f"Competitor{i}") for i in range(competitor_agent._MAX_ENRICHED + 2)]
        competitor_agent._enrich_with_apis(competitors)
        enriched_count = sum(1 for c in competitors if "enrichment" in c)
        self.assertEqual(enriched_count, competitor_agent._MAX_ENRICHED)


if __name__ == "__main__":
    unittest.main()
