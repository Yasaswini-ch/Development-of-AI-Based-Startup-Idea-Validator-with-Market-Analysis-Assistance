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

    def test_competitor_queries_lead_with_the_unbranded_domain_query(self):
        angles = dict(retrieval.build_search_angles(*SHIFTSPEAK))
        first = angles["Competitors"][0]
        self.assertNotIn("ShiftSpeak", first)
        self.assertIn("patients", first)
        self.assertTrue(first.endswith("alternatives"))
        # The brand-prefixed queries are still there as fallbacks.
        self.assertTrue(any("ShiftSpeak" in q for q in angles["Competitors"]))


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
