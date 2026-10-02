"""Junk competitor names and non-English quotes that real runs let through."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("WEB_CACHE", "0")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import competitor_agent, voice_of_market


class JunkCompetitorNameTests(unittest.TestCase):
    def test_page_chrome_and_review_sites_are_not_competitors(self):
        for name in ("Chrome", "Google Chrome", "Key Features", "Capterra", "G2", "Trustpilot", "Gartner", "PCMag", "CNET"):
            self.assertTrue(competitor_agent._is_generic_phrase(name), name)

    def test_marketplace_category_headings_stay_filtered(self):
        for name in ("DEVELOPMENT & IT", "DESIGN & CREATIVE"):
            self.assertTrue(competitor_agent._is_generic_phrase(name), name)

    def test_real_competitors_are_still_kept(self):
        for name in ("FreshBooks", "Harvest", "Clockify", "Toggl", "HoneyBook", "QuickBooks", "Avaza", "Toptal"):
            self.assertFalse(competitor_agent._is_generic_phrase(name), name)


class EnglishQuoteTests(unittest.TestCase):
    def test_english_sentences_pass(self):
        for text in (
            "Freelancers waste hours on manual invoicing and struggle to get paid on time.",
            "I wish there was a tool that could chase late payments for me.",
            "The market is growing at 12% a year, and it is expected to reach $15 billion.",
        ):
            self.assertTrue(voice_of_market._looks_english(text), text)

    def test_portuguese_spanish_french_german_are_rejected(self):
        for text in (
            "O problema é que esta é uma das opções mais caras do mercado para quem trabalha por conta própria.",
            "El problema es que los autónomos pierden horas en la facturación y no cobran a tiempo.",
            "Le problème est que les freelances perdent des heures avec la facturation des clients.",
            "Das Problem ist, dass Freiberufler Stunden mit der Rechnungsstellung verlieren und nicht bezahlt werden.",
        ):
            self.assertFalse(voice_of_market._looks_english(text), text)

    def test_non_latin_scripts_are_rejected(self):
        for text in ("自由职业者在发票和时间跟踪上浪费了大量时间，而且常常无法按时收款。", "Фрилансеры тратят часы на выставление счетов и ждут оплату."):
            self.assertFalse(voice_of_market._looks_english(text), text)

    def test_a_short_plain_english_sentence_is_kept(self):
        self.assertTrue(voice_of_market._looks_english("We doubled our revenue in six months."))

    def test_accented_text_with_no_english_word_is_rejected(self):
        self.assertFalse(voice_of_market._looks_english("Freelancers odeiam faturação manual e perdem horas preciosas"))

    def test_extraction_drops_a_foreign_quote_and_keeps_the_english_one(self):
        results = [
            {"title": "Forum", "url": "https://forum.example/a", "snippet": "O problema é que esta é uma das opções mais caras do mercado para quem trabalha por conta própria."},
            {"title": "Blog", "url": "https://blog.example/b", "snippet": "Freelancers struggle with manual invoicing and it wastes a lot of their time every week."},
        ]
        quotes = voice_of_market.extract_voice_of_market(results)
        self.assertEqual([q["sourceId"] for q in quotes], ["src-2"])


if __name__ == "__main__":
    unittest.main()
