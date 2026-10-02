"""Tests for competitor_agent.py's grounded LLM discovery pass
(_discover_with_llm, _ground_and_clean_competitors) and how
analyze_competitors merges it with the NER-only list - see
docs/competitor-detection-and-confidence-scoring-proposal.md Option B.

Standalone like test_competitor_profiling.py: exercises the pure
shape-validation/grounding helpers directly, without needing a real LLM
call, plus one analyze_competitors-level test with _discover_with_llm
mocked to check the union/merge behavior.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("WEB_CACHE", "0")  # tests must never read or write the shared lookup cache (agent/web_cache.py)
sys.path.insert(0, str(BACKEND_DIR))

from agent import competitor_agent


def _source(text, url="https://example.com"):
    return {"text": text, "result": {"url": url, "snippet": text}}


class IsGenericPhraseTests(unittest.TestCase):
    def test_rejects_ampersand_joined_category_labels(self):
        self.assertTrue(competitor_agent._is_generic_phrase("Development & IT"))
        self.assertTrue(competitor_agent._is_generic_phrase("Design & Creative"))

    def test_keeps_real_brand_names(self):
        self.assertFalse(competitor_agent._is_generic_phrase("HelloFresh"))
        self.assertFalse(competitor_agent._is_generic_phrase("Freelancer.com"))
        self.assertFalse(competitor_agent._is_generic_phrase("QuickBooks Online"))


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
    def test_keeps_a_name_not_present_in_its_cited_source(self):
        # Relaxed by product decision (Sept 2026): a competitor no longer
        # needs its name to literally appear in the cited source's text -
        # only a valid sourceId, so the model can name a real competitor
        # it recognizes from general knowledge even when the specific
        # snippet didn't happen to spell it out. See
        # _ground_and_clean_competitors' docstring.
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [{"name": "Blue Apron", "sourceIds": ["r1"], "classification": "direct"}]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["name"], "Blue Apron")

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
        # One more candidate than the cap, so this still exercises capping
        # itself rather than assuming a specific cap value.
        count = competitor_agent._MAX_COMPETITORS + 1
        sources = {
            f"r{i}": _source(f"Competitor{i} is a popular meal kit service.") for i in range(1, count + 1)
        }
        raw = [{"name": f"Competitor{i}", "sourceIds": [f"r{i}"]} for i in range(1, count + 1)]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(len(cleaned), competitor_agent._MAX_COMPETITORS)

    def test_missing_gap_falls_back_to_disclosure(self):
        sources = {"r1": _source("HelloFresh charges $60/week for meal kits.")}
        raw = [{"name": "HelloFresh", "sourceIds": ["r1"]}]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual(cleaned[0]["gap"], competitor_agent._GAP_DISCLOSURE)

    def test_drops_a_marketplace_category_label_masquerading_as_a_name(self):
        # Confirmed live: Freelancer.com/Toptal's own site nav ("Development
        # & IT", "Design & Creative") got extracted as if they were
        # competitor brands, since the discovery LLM only checks that a
        # name literally appears in its cited source's text - which a nav
        # label does, just as much as a real company name would.
        sources = {"r1": _source("Browse categories: Development & IT, Design & Creative, and more on Freelancer.com.")}
        raw = [
            {"name": "Development & IT", "sourceIds": ["r1"]},
            {"name": "Design & Creative", "sourceIds": ["r1"]},
            {"name": "Freelancer.com", "sourceIds": ["r1"]},
        ]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        self.assertEqual([c["name"] for c in cleaned], ["Freelancer.com"])

    def test_price_not_misattributed_across_a_whole_multi_competitor_source(self):
        # Regression: a single shared source naming several competitors used
        # to give ALL of them the SAME estimatedPrice (whichever was
        # cheapest anywhere in the whole source text), because the price
        # heuristic ran over the entire source instead of just the text
        # near each name. A third, unrelated sentence keeps this source's
        # cheapest price ($8) away from Blue Apron's own line entirely, so
        # this isolates the "whole source" bug from the narrower
        # immediately-adjacent-sentence case _local_text_near_name still
        # allows (see LocalTextNearNameTests).
        sources = {
            "r1": _source(
                "Onyx costs $8 a month, a budget option. "
                "This roundup also covers several other tools in the space. "
                "Blue Apron costs $120 a month, a premium option."
            )
        }
        raw = [
            {"name": "Onyx", "sourceIds": ["r1"], "classification": "direct"},
            {"name": "Blue Apron", "sourceIds": ["r1"], "classification": "direct"},
        ]
        cleaned = competitor_agent._ground_and_clean_competitors(raw, sources)
        by_name = {c["name"]: c for c in cleaned}
        self.assertEqual(by_name["Onyx"]["estimatedPrice"], "low")
        self.assertEqual(by_name["Blue Apron"]["estimatedPrice"], "high")


class LocalTextNearNameTests(unittest.TestCase):
    def test_scopes_away_from_a_non_adjacent_sentence(self):
        text = "Onyx costs $8 a month. Unrelated filler sentence here. Blue Apron costs $120 a month."
        scoped = competitor_agent._local_text_near_name(text, "Onyx")
        self.assertIn("Onyx", scoped)
        self.assertIn("$8", scoped)
        self.assertNotIn("$120", scoped)

    def test_can_still_include_an_immediately_following_sentence(self):
        # Known, accepted tradeoff (same as _local_context): the window
        # includes the sentence right after the name's own sentence, so a
        # comparison-table row split across two lines ("Name. $Price.")
        # still gets its price - even when that next sentence happens to
        # be a different competitor's own line.
        text = "Onyx costs $8 a month. Blue Apron costs $120 a month."
        scoped = competitor_agent._local_text_near_name(text, "Onyx")
        self.assertIn("$120", scoped)

    def test_falls_back_to_full_text_when_name_not_found(self):
        text = "Some unrelated text."
        self.assertEqual(competitor_agent._local_text_near_name(text, "Nope"), text)


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

    @patch("agent.competitor_agent._discover_with_llm")
    def test_falls_back_to_deterministic_matrix_when_discovery_matrix_is_empty(self, mock_discover):
        # Discovery found competitors but its own comparisonMatrix came back
        # empty (e.g. the model omitted it, or the discovery call failed
        # entirely and only the NER-only list is available) - the report
        # must still show a comparison rather than nothing.
        mock_discover.return_value = None
        results = [
            {
                "angle": "Competitors",
                "title": "HelloFresh review",
                "snippet": (
                    "HelloFresh is a popular meal kit service charging $60/week for "
                    "weekly boxes. Many customers switch from HelloFresh to cheaper options."
                ),
                "url": "https://example.com/roundup",
            }
        ]
        result = competitor_agent.analyze_competitors(
            "Meal kits", "Busy parents", "No time to cook", results, profile=True
        )
        self.assertTrue(result["competitors"])
        self.assertTrue(result["comparisonMatrix"])
        dimensions = {row["dimension"] for row in result["comparisonMatrix"]}
        self.assertTrue({"Price", "Feature breadth", "Positioning"} <= dimensions)
        for row in result["comparisonMatrix"]:
            for name in {c["name"] for c in result["competitors"]}:
                self.assertIn(name, row["competitors"])


class BuildFallbackMatrixTests(unittest.TestCase):
    def test_empty_without_competitors(self):
        self.assertEqual(competitor_agent._build_fallback_matrix([]), [])

    def test_builds_the_three_core_rows_when_nothing_else_is_known(self):
        competitors = [
            {"name": "HelloFresh", "estimatedPrice": "high", "featureBreadth": "broad", "classification": "direct"},
            {"name": "Obscurename", "estimatedPrice": "unknown", "featureBreadth": "unknown", "classification": "unknown"},
        ]
        matrix = competitor_agent._build_fallback_matrix(competitors)
        self.assertEqual(len(matrix), 3)
        by_dimension = {row["dimension"]: row for row in matrix}
        self.assertEqual(by_dimension["Price"]["competitors"]["HelloFresh"], "High (over $25/mo)")
        self.assertEqual(by_dimension["Price"]["competitors"]["Obscurename"], "unknown")
        # Never invents data about the idea itself - only honest, generic
        # pre-launch language, never a fabricated price/feature claim.
        for row in matrix:
            self.assertIn("idea", row)
            self.assertNotIn("$", row["idea"])


class RichComparisonMatrixTests(unittest.TestCase):
    RIVALS = [
        {
            "name": "Harvest",
            "classification": "direct",
            "estimatedPrice": "mid",
            "featureBreadth": "broad",
            "offering": "Time tracking and invoicing for freelancers and small teams.",
            "businessModel": "subscription",
            "pricing": "$12/mo, free tier",
            "strengths": ["Simple timers", "Invoices from tracked time"],
            "weaknesses": ["No late-payment reminders"],
            "enrichment": {"source": "itunes", "averageRating": 4.49, "ratingCount": 12345},
        },
        {
            "name": "FreshBooks",
            "classification": "direct",
            "estimatedPrice": "unknown",
            "featureBreadth": "unknown",
            "offering": "Accounting and invoicing software.",
            "businessModel": "unknown",
            "pricing": "unknown",
            "strengths": [],
            "weaknesses": [],
            "enrichment": {"source": "wikidata", "foundedYear": 2003},
        },
    ]

    def test_fallback_grows_to_eight_rows_from_real_data(self):
        matrix = competitor_agent._build_fallback_matrix(self.RIVALS, "An app that tracks time and chases late payments. More text.")
        dims = [r["dimension"] for r in matrix]
        self.assertEqual(len(matrix), 8)
        self.assertEqual(dims[:3], ["Price", "Feature breadth", "Positioning"])
        for expected in ("What it offers", "Business model", "Main strength", "Main weakness", "Customer rating"):
            self.assertIn(expected, dims)
        by = {r["dimension"]: r for r in matrix}
        self.assertEqual(by["Customer rating"]["competitors"]["Harvest"], "4.5/5 from 12,345 ratings")
        self.assertEqual(by["Customer rating"]["competitors"]["FreshBooks"], "unknown")
        self.assertEqual(by["Main strength"]["competitors"]["Harvest"], "Simple timers")
        self.assertEqual(by["What it offers"]["idea"], "An app that tracks time and chases late payments")

    def test_a_row_with_no_data_for_any_rival_is_left_out(self):
        bare = [{"name": "A", "classification": "direct"}, {"name": "B", "classification": "direct"}]
        self.assertEqual([r["dimension"] for r in competitor_agent._build_fallback_matrix(bare)], ["Price", "Feature breadth", "Positioning"])

    def test_idea_cells_never_invent_a_price_or_a_claim(self):
        for row in competitor_agent._build_fallback_matrix(self.RIVALS, "An app"):
            self.assertNotIn("$", row["idea"])

    def test_columns_are_the_closest_eight_rivals(self):
        rivals = [{"name": f"I{i}", "classification": "indirect"} for i in range(6)] + [
            {"name": f"D{i}", "classification": "direct"} for i in range(5)
        ]
        names = list(competitor_agent._build_fallback_matrix(rivals)[0]["competitors"])
        self.assertEqual(len(names), 8)
        self.assertEqual([n for n in names if n.startswith("D")], [f"D{i}" for i in range(5)])  # all direct rivals kept

    def test_a_short_model_matrix_is_topped_up_without_changing_its_rows(self):
        model_rows = [
            {"dimension": "Price", "idea": "Freemium", "competitors": {"Harvest": "$12/mo", "FreshBooks": "$19/mo"}},
            {"dimension": "Core feature", "idea": "Chases late payments", "competitors": {"Harvest": "Timers", "FreshBooks": "Invoices"}},
        ]
        padded = competitor_agent._pad_matrix(model_rows, self.RIVALS, "An app")
        self.assertEqual(padded[:2], model_rows)
        self.assertEqual(len(padded), 6)
        self.assertEqual([r["dimension"] for r in padded].count("Price"), 1)  # no duplicate of a dimension the model covered

    def test_a_matrix_that_is_already_long_enough_is_untouched(self):
        rows = [{"dimension": f"D{i}", "idea": "x", "competitors": {"Harvest": "y"}} for i in range(6)]
        self.assertEqual(competitor_agent._pad_matrix(rows, self.RIVALS), rows)


if __name__ == "__main__":
    unittest.main()


class ClassifyCompetitorTests(unittest.TestCase):
    """Fallback-path direct/indirect labelling. It used to call every
    competitor "direct" because it matched generic/customer words and the
    whole shared listicle snippet; these pin the stricter behaviour."""

    KEYWORDS = {"freelancers", "invoicing", "invoices", "payments", "tracking", "clients", "hours", "time"}
    CUSTOMER = "Freelancers and independent contractors"

    def _label(self, text):
        return competitor_agent._classify_competitor(self.KEYWORDS, text, exclude_terms=self.CUSTOMER)

    def test_two_distinct_job_topics_is_direct(self):
        self.assertEqual(self._label("Clockify offers time tracking and sends invoices."), "direct")

    def test_one_job_topic_is_indirect(self):
        self.assertEqual(self._label("PayPal lets anyone accept payments online."), "indirect")

    def test_only_generic_or_customer_words_is_unknown(self):
        # "freelancers", "clients", "hours", "time" are all ignored, so a
        # page that merely talks about the audience is not a rival.
        self.assertEqual(self._label("Great for freelancers who bill clients by the hour, saving time."), "unknown")

    def test_word_variants_count_once(self):
        # invoice/invoices/invoicing are one topic, so this is one match, not three.
        self.assertEqual(self._label("Send an invoice, then another invoice, then invoicing reports."), "indirect")

    def test_no_keywords_is_unknown(self):
        self.assertEqual(competitor_agent._classify_competitor(set(), "anything at all"), "unknown")


class NearMatchDedupeCaseTests(unittest.TestCase):
    def test_spellings_that_differ_only_by_case_are_one_company(self):
        kept = competitor_agent._dedupe_near_matches({"Toptal": {"count": 3}, "TopTal": {"count": 1}, "Contra": {"count": 1}})
        self.assertEqual(sorted(k.lower() for k in kept), ["contra", "toptal"])
        self.assertIn("Toptal", kept)  # the most-mentioned spelling wins
