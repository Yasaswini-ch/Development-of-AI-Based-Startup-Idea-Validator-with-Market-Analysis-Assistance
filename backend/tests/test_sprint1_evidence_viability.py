"""Contract tests for Sprint 1 of the 5-pillar spec: Pillar 1 (voice-of-
market excerpts + provenance) and Pillar 2 (Market Viability & Dynamics
Index).

Standalone like test_viability_score.py: only imports the pure modules
(no fastapi/langgraph/crewai needed).
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.output_guard import provenance
from agent.viability_score import calculate_viability_index
from agent.voice_of_market import (
    MAX_QUOTES,
    extract_voice_of_market,
    extract_voice_of_owner,
    summarize_voice_of_market,
    summarize_voice_of_owner,
)

_QUOTE_KEYS = {"quote", "speakerOrSource", "sourceId", "url", "sentiment", "taggedDimension", "theme"}
_DIMENSION_NAMES = [
    "Demand Urgency",
    "Expansion Velocity",
    "Target Accessibility",
    "Barrier to Entry / Moat",
    "Capital Efficiency",
]

_RESULTS = [
    {
        "title": "Global invoicing software market report",
        "url": "https://example.com/report",
        "snippet": "The invoicing software market is growing at 12% CAGR and is expected to reach $5 billion by 2030.",
    },
    {
        "title": "Ask r/freelance: invoicing",
        "url": "https://www.reddit.com/r/freelance/comments/abc",
        "snippet": "Honestly I hate how tedious it is to chase multi-client payouts every month. Any tips?",
    },
    {
        "title": "Show HN",
        "url": "https://news.ycombinator.com/item?id=1",
        "snippet": "Short.",
    },
    {
        "title": "Freelancer survey",
        "url": "https://survey.example.org/freelancers",
        "snippet": "Most freelancers said they are looking for a simpler way to split payments with collaborators.",
    },
]


class VoiceOfMarketTests(unittest.TestCase):
    def test_quotes_match_the_contract_shape(self):
        quotes = extract_voice_of_market(_RESULTS)
        self.assertTrue(quotes)
        for quote in quotes:
            self.assertEqual(set(quote), _QUOTE_KEYS)
            self.assertRegex(quote["sourceId"], r"^src-\d+$")

    def test_quotes_are_verbatim_from_the_cited_snippet(self):
        for quote in extract_voice_of_market(_RESULTS):
            index = int(quote["sourceId"].split("-")[1]) - 1
            self.assertIn(quote["quote"], _RESULTS[index]["snippet"])
            self.assertEqual(quote["url"], _RESULTS[index]["url"])

    def test_friction_quotes_rank_first_and_are_negative(self):
        first = extract_voice_of_market(_RESULTS)[0]
        self.assertEqual(first["taggedDimension"], "Observed Friction")
        self.assertEqual(first["sentiment"], "negative_towards_incumbent")
        self.assertEqual(first["speakerOrSource"], "Reddit thread")

    def test_too_short_snippets_are_skipped(self):
        ids = {q["sourceId"] for q in extract_voice_of_market(_RESULTS)}
        self.assertNotIn("src-3", ids)

    def test_at_most_one_quote_per_source_and_capped(self):
        many = [dict(_RESULTS[1], url=f"https://reddit.com/{i}") for i in range(MAX_QUOTES + 10)]
        quotes = extract_voice_of_market(many)
        self.assertEqual(len(quotes), MAX_QUOTES)
        self.assertEqual(len({q["sourceId"] for q in quotes}), MAX_QUOTES)

    def test_a_dimension_with_fewer_candidates_is_not_starved_out_by_the_cap(self):
        # Regression: friction (18) + demand (18) alone exceed MAX_QUOTES, so a
        # plain sort-then-slice would drop every tailwind quote even though
        # tailwind candidates exist - the summary would then report a nonzero
        # count for a dimension with zero quotes and no filter tab to show it.
        friction = [
            {"url": f"https://a.example/{i}", "snippet": "It is so tedious and frustrating to chase late payments every month."}
            for i in range(18)
        ]
        demand = [
            {"url": f"https://b.example/{i}", "snippet": "I am looking for a simpler alternative to what we use today."}
            for i in range(18)
        ]
        tailwind = [
            {"url": f"https://c.example/{i}", "snippet": "The market is growing fast and adoption keeps rising every quarter."}
            for i in range(5)
        ]
        quotes = extract_voice_of_market(friction + demand + tailwind)
        dimensions_present = {q["taggedDimension"] for q in quotes}
        self.assertIn("Structural Tailwind", dimensions_present)

    def test_theme_is_tagged_from_the_sentence_content(self):
        results = [
            {"url": "https://a.example/1", "snippet": "The pricing is way too expensive for what you get every month."},
            {"url": "https://b.example/2", "snippet": "Integrating with our existing API was so difficult and confusing it took weeks."},
        ]
        quotes = {q["sourceId"]: q for q in extract_voice_of_market(results)}
        self.assertEqual(quotes["src-1"]["theme"], "Pricing & Cost")
        self.assertEqual(quotes["src-2"]["theme"], "Integrations & Compatibility")

    def test_theme_falls_back_to_general(self):
        first = extract_voice_of_market(_RESULTS)[0]
        self.assertIn(first["theme"], {"General", "Pricing & Cost", "Integrations & Compatibility",
                                        "Reliability & Support", "Onboarding & Usability",
                                        "Competition & Alternatives"})

    def test_no_usable_snippets_returns_empty_list(self):
        self.assertEqual(extract_voice_of_market([]), [])
        self.assertEqual(extract_voice_of_market([{"snippet": "Nothing relevant here at all, just words."}]), [])
        self.assertEqual(extract_voice_of_market(None), [])


_OWNER_RESULTS = [
    {
        "url": "https://a.example/hiring",
        "snippet": "As a small SaaS founder, it's been hard to hire good engineers who can also do support.",
    },
    {
        "url": "https://b.example/growth",
        "snippet": "We scaled our invoicing startup to $40k MRR within a year of launch.",
    },
    {
        "url": "https://c.example/pivot",
        "snippet": "We pivoted our billing product twice before finding a market that would actually pay.",
    },
    {
        "url": "https://d.example/customer",
        "snippet": "I hate how tedious it is to chase multi-client payouts every single month for my freelance work.",
    },
]


class VoiceOfOwnerTests(unittest.TestCase):
    def test_quotes_match_the_contract_shape(self):
        quotes = extract_voice_of_owner(_OWNER_RESULTS)
        self.assertTrue(quotes)
        for quote in quotes:
            self.assertEqual(set(quote), _QUOTE_KEYS)

    def test_operational_friction_ranks_first_and_is_negative(self):
        first = extract_voice_of_owner(_OWNER_RESULTS)[0]
        self.assertEqual(first["taggedDimension"], "Operational Friction")
        self.assertEqual(first["sentiment"], "negative_towards_incumbent")

    def test_growth_quote_is_positive(self):
        quotes = {q["sourceId"]: q for q in extract_voice_of_owner(_OWNER_RESULTS)}
        self.assertEqual(quotes["src-2"]["taggedDimension"], "Growth & Traction")
        self.assertEqual(quotes["src-2"]["sentiment"], "positive_market_signal")

    def test_customer_side_sentence_is_not_picked_up_as_owner_voice(self):
        ids = {q["sourceId"] for q in extract_voice_of_owner(_OWNER_RESULTS)}
        self.assertNotIn("src-4", ids)

    def test_owner_and_customer_extraction_are_independent(self):
        # The customer-side extractor should not surface the owner-only quotes either.
        ids = {q["sourceId"] for q in extract_voice_of_market(_OWNER_RESULTS)}
        self.assertIn("src-4", ids)
        self.assertNotIn("src-2", ids)

    def test_no_usable_snippets_returns_empty_list(self):
        self.assertEqual(extract_voice_of_owner([]), [])
        self.assertEqual(extract_voice_of_owner(None), [])


class VoiceOfOwnerSummaryTests(unittest.TestCase):
    def test_counts_every_owner_dimension(self):
        summary = summarize_voice_of_owner(_OWNER_RESULTS)
        self.assertEqual(
            set(summary["dimensionCounts"]),
            {"Operational Friction", "Growth & Traction", "Strategic Signal"},
        )
        self.assertGreaterEqual(summary["sourcesWithSignal"], 3)

    def test_every_dimension_key_present_even_when_zero(self):
        summary = summarize_voice_of_owner([])
        self.assertEqual(
            summary["dimensionCounts"],
            {"Operational Friction": 0, "Growth & Traction": 0, "Strategic Signal": 0},
        )


class VoiceOfMarketSummaryTests(unittest.TestCase):
    def test_counts_every_tagged_sentence_not_just_the_capped_quotes(self):
        total = MAX_QUOTES + 10
        many = [dict(_RESULTS[1], url=f"https://reddit.com/{i}") for i in range(total)]
        summary = summarize_voice_of_market(many)
        self.assertEqual(summary["dimensionCounts"]["Observed Friction"], total)
        self.assertEqual(summary["sourcesWithSignal"], total)
        self.assertEqual(summary["sourcesScanned"], total)
        # extract_voice_of_market caps to MAX_QUOTES, but the summary must not.
        self.assertGreater(summary["sourcesWithSignal"], len(extract_voice_of_market(many)))

    def test_every_dimension_key_present_even_when_zero(self):
        summary = summarize_voice_of_market([])
        self.assertEqual(
            summary["dimensionCounts"],
            {"Observed Friction": 0, "Demand Signal": 0, "Structural Tailwind": 0},
        )
        self.assertEqual(summary["sourcesScanned"], 0)
        self.assertEqual(summary["sourcesWithSignal"], 0)

    def test_handles_none_and_non_dict_results(self):
        self.assertEqual(summarize_voice_of_market(None)["sourcesScanned"], 0)


class ProvenanceTests(unittest.TestCase):
    def test_grounded_when_any_source_is_cited(self):
        self.assertEqual(provenance(["src-1", "src-2"]), {"status": "grounded", "sourceCount": 2})

    def test_inferred_when_no_sources(self):
        self.assertEqual(provenance([]), {"status": "inferred", "sourceCount": 0})
        self.assertEqual(provenance(None), {"status": "inferred", "sourceCount": 0})


_MARKET = {
    "marketSize": "The global market is worth billions and growing rapidly.",
    "trends": [
        {"text": "Rising demand for split payouts", "sourceIds": ["src-1"]},
        {"text": "Growing adoption of fractional hiring", "sourceIds": []},
    ],
    "tam": {"text": "$5 billion by 2030", "sourceIds": ["src-1"]},
    "sam": None,
    "som": None,
    "segments": [
        {
            "segment": "Freelance collectives",
            "painPoints": "Chasing payouts",
            "motivations": "Save time",
            "buyingBehavior": "Try free tools found in communities before paying",
            "sourceIds": ["src-2"],
        },
        {
            "segment": "Agencies",
            "painPoints": "Reconciliation",
            "motivations": "Accuracy",
            "buyingBehavior": "Not clear from the sources",
            "sourceIds": [],
        },
    ],
}


class ViabilityIndexTests(unittest.TestCase):
    def _index(self, **overrides):
        market = {**_MARKET, "voiceOfMarket": extract_voice_of_market(_RESULTS)}
        kwargs = {
            "swot_data": {"risks": [{"risk": "Stripe platform risk", "severity": "medium", "likelihood": "low", "sourceIds": ["src-4"]}]},
            "competitors_data": {"competitors": [{"name": "Acme", "url": "https://example.com/report"}]},
            "results": _RESULTS,
            "idea": "A SaaS app for freelance collectives to split invoices",
        }
        kwargs.update(overrides)
        return calculate_viability_index(market, **kwargs)

    def test_has_exactly_five_named_dimensions_in_order(self):
        index = self._index()
        self.assertEqual([d["name"] for d in index["dimensions"]], _DIMENSION_NAMES)

    def test_every_dimension_matches_the_contract(self):
        for dim in self._index()["dimensions"]:
            self.assertIn(dim["score"], range(1, 6))
            self.assertEqual(dim["rating"], {1: "Low", 2: "Low", 3: "Medium", 4: "High", 5: "High"}[dim["score"]])
            self.assertIsInstance(dim["rationale"], str)
            self.assertTrue(dim["rationale"].strip())
            self.assertIsInstance(dim["sourceIds"], list)
            self.assertEqual(dim["provenance"], provenance(dim["sourceIds"]))

    def test_composite_score_is_mean_axis_score_on_0_100(self):
        index = self._index()
        expected = round(sum(d["score"] for d in index["dimensions"]) / 25 * 100)
        self.assertEqual(index["compositeScore"], expected)
        self.assertGreaterEqual(index["compositeScore"], 0)
        self.assertLessEqual(index["compositeScore"], 100)

    def test_source_ids_are_real_and_deduplicated(self):
        valid = {f"src-{i}" for i in range(1, len(_RESULTS) + 1)}
        for dim in self._index()["dimensions"]:
            self.assertTrue(set(dim["sourceIds"]) <= valid, dim)
            self.assertEqual(len(dim["sourceIds"]), len(set(dim["sourceIds"])))

    def test_competitor_urls_resolve_to_source_ids(self):
        moat = self._index()["dimensions"][3]
        self.assertIn("src-1", moat["sourceIds"])
        self.assertIn("src-4", moat["sourceIds"])

    def test_capital_efficiency_is_always_labelled_inferred(self):
        capital = self._index()["dimensions"][4]
        self.assertEqual(capital["sourceIds"], [])
        self.assertEqual(capital["provenance"]["status"], "inferred")

    def test_software_idea_is_more_capital_efficient_than_hardware(self):
        software = self._index(idea="An AI app for invoicing")["dimensions"][4]["score"]
        hardware = self._index(idea="A wearable hardware device for invoicing")["dimensions"][4]["score"]
        self.assertGreater(software, hardware)

    def test_empty_inputs_degrade_gracefully(self):
        index = calculate_viability_index(None)
        self.assertEqual(len(index["dimensions"]), 5)
        for dim in index["dimensions"]:
            self.assertIn(dim["score"], range(1, 6))


if __name__ == "__main__":
    unittest.main()
