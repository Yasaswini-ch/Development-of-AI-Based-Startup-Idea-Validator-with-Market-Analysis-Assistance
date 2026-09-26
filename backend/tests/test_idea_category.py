"""Tests for agent/idea_category.py's keyword-based categorizer."""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.idea_category import categorize_idea


class CategorizeIdeaTests(unittest.TestCase):
    def test_meal_planning_app_is_food(self):
        self.assertEqual(categorize_idea("An AI-powered meal planning app for busy families"), "Food & Meal Prep")

    def test_invoicing_saas_is_fintech_not_saas(self):
        # More specific category wins even though "invoicing automation
        # SaaS" also matches the SaaS/B2B keyword list.
        self.assertEqual(categorize_idea("B2B invoicing automation SaaS for freelancers"), "Fintech")

    def test_generic_b2b_tool_is_saas(self):
        self.assertEqual(categorize_idea("A workflow automation dashboard for enterprise teams"), "SaaS / B2B Tools")

    def test_unmatched_idea_falls_back_to_other(self):
        self.assertEqual(categorize_idea("A birdwatching social network"), "Other")

    def test_empty_idea_falls_back_to_other(self):
        self.assertEqual(categorize_idea(""), "Other")
        self.assertEqual(categorize_idea(None), "Other")

    def test_case_insensitive(self):
        self.assertEqual(categorize_idea("A FITNESS AND WELLNESS APP"), "Consumer Health")


if __name__ == "__main__":
    unittest.main()
