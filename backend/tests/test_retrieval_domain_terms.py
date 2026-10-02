import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import retrieval

SHIFTSPEAK = (
    "ShiftSpeak is a mobile app that teaches nurses and care workers the exact phrases they need to talk with "
    "patients in another language (Spanish first). The app lets users practise by voice and gives instant "
    "feedback on pronunciation. Hospitals can buy team licences and track which staff have completed modules.",
    "Nurses and home-care workers in US hospitals who regularly treat Spanish-speaking patients.",
    "Interpreter services are slow, and general language apps like Duolingo teach travel phrases, not clinical "
    "conversations. Misunderstandings with patients cause errors, and hospitals cannot track language skills.",
)


class DomainTermTests(unittest.TestCase):
    def test_terms_repeated_across_fields_beat_a_long_passing_word(self):
        terms = retrieval._domain_terms(*SHIFTSPEAK)
        self.assertIn("patients", terms)
        self.assertNotIn("pronunciation", terms)

    def test_no_terms_when_nothing_repeats_across_fields(self):
        self.assertEqual(retrieval._domain_terms("alpha bravo", "charlie delta", "echo foxtrot"), [])

    def test_competitor_queries_lead_with_the_unbranded_product_query(self):
        angles = dict(retrieval.build_search_angles(*SHIFTSPEAK))
        first = angles["Competitors"][0]
        self.assertNotIn("ShiftSpeak", first)
        self.assertTrue(first.endswith("alternatives"))
        # The unbranded domain-term query and the brand-prefixed ones are still
        # there as fallbacks.
        self.assertTrue(any("patients" in q and "ShiftSpeak" not in q for q in angles["Competitors"]))
        self.assertTrue(any("ShiftSpeak" in q for q in angles["Competitors"]))


class WhatItDoesTests(unittest.TestCase):
    def test_a_freelancer_invoicing_idea_searches_for_the_job_not_the_customer(self):
        core = retrieval._what_it_does(
            "An AI-powered app that helps freelancers automatically track time, generate invoices, and chase late payments from clients"
        )
        self.assertIn("track time", core)
        self.assertIn("invoices", core)
        self.assertNotEqual(core, "freelancers")

    def test_a_brand_introduction_is_removed(self):
        core = retrieval._what_it_does("ShiftSpeak is a mobile app that teaches nurses medical Spanish phrases. More text here.")
        self.assertNotIn("ShiftSpeak", core)
        self.assertTrue(core.startswith("teaches nurses"))

    def test_only_the_first_sentence_is_used(self):
        core = retrieval._what_it_does("A tool that turns support calls into a digest. Hospitals can buy licences.")
        self.assertEqual(core, "turns support calls into a digest")

    def test_trailing_filler_words_are_trimmed(self):
        core = retrieval._what_it_does("An app that lets people split restaurant bills and", max_words=8)
        self.assertFalse(core.endswith("and"))

    def test_nothing_usable_returns_an_empty_string(self):
        self.assertEqual(retrieval._what_it_does(""), "")
        self.assertEqual(retrieval._what_it_does("An app that"), "")

    def test_product_queries_lead_the_competitor_angle_for_a_non_branded_idea(self):
        angles = dict(
            retrieval.build_search_angles(
                "An AI-powered app that helps freelancers automatically track time, generate invoices, and chase late payments from clients",
                "Freelancers and independent contractors",
                "Freelancers waste hours on manual time tracking and invoicing",
            )
        )
        first, second = angles["Competitors"][:2]
        self.assertIn("track time", first)
        self.assertTrue(first.endswith("alternatives"))
        self.assertTrue(second.startswith("best "))
        self.assertIn("freelancers alternatives", angles["Competitors"])  # the old query is kept as a fallback


class FallbackThreatTests(unittest.TestCase):
    def _threats(self, competitors):
        from agent.deterministic_fallback import deterministic_swot

        swot = deterministic_swot("Idea", None, {"competitors": competitors}, {}, [])
        return [t["text"] for t in swot["threats"]]

    def test_shared_list_snippet_is_not_repeated_for_every_competitor(self):
        snippet = "Best pronunciation apps: SpeakShark isn't close among pronunciation-focused apps."
        competitors = [
            {"name": n, "offering": snippet, "url": "https://x.com"} for n in ("ELSA Speak", "TalkPal", "BoldVoice")
        ]
        threats = self._threats(competitors)
        self.assertEqual(len(threats), 3)
        self.assertFalse(any("SpeakShark" in t for t in threats))
        self.assertTrue(all("appears in the sources" in t for t in threats))

    def test_an_offering_that_names_the_competitor_is_still_quoted(self):
        competitors = [{"name": "Lingo", "offering": "Lingo teaches medical Spanish.", "url": "https://x.com"}]
        self.assertIn("Lingo teaches medical Spanish", self._threats(competitors)[0])


if __name__ == "__main__":
    unittest.main()
