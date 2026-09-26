"""Tests for the assumption tracker's parsing and deterministic fallback."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.assumption_agent import _usable_assumptions, analyze_assumptions
from agent.deterministic_fallback import deterministic_assumptions

_CATEGORIES = {"demand", "market", "technical", "competitive", "regulatory"}
_UNCERTAINTIES = {"high", "medium", "low"}


class AssumptionParsingTests(unittest.TestCase):
    def test_capitalised_enums_are_accepted_and_invalid_items_dropped(self):
        value = {
            "assumptions": [
                {"assumption": "Buyers will pay", "category": "Demand", "uncertainty": "High", "howToValidate": "Pre-sell"},
                {"assumption": "", "category": "market", "uncertainty": "low", "howToValidate": "x"},
            ]
        }
        usable = _usable_assumptions(value)
        self.assertEqual(len(usable), 1)
        self.assertEqual(usable[0]["category"], "demand")
        self.assertEqual(usable[0]["uncertainty"], "high")


class AssumptionFallbackTests(unittest.TestCase):
    def test_llm_failure_returns_deterministic_assumptions_not_an_empty_list(self):
        with patch("agent.assumption_agent.kickoff_with_fallback", side_effect=RuntimeError("quota")):
            result = analyze_assumptions(
                "Invoice reminders for freelancers", "freelancers", "late invoices",
                {"threats": []}, {"trends": []}, {"features": [{"feature": "Auto reminders"}]}, [],
                allow_local=True,
            )
        self.assertTrue(result["degraded"])
        self.assertGreaterEqual(len(result["assumptions"]), 4)

    def test_fallback_assumptions_match_the_real_contract(self):
        result = deterministic_assumptions("A telehealth app", "patients", "long waits", None, None, None)
        categories = {a["category"] for a in result["assumptions"]}
        self.assertIn("regulatory", categories)
        for item in result["assumptions"]:
            self.assertIn(item["category"], _CATEGORIES)
            self.assertIn(item["uncertainty"], _UNCERTAINTIES)
            self.assertTrue(item["assumption"].strip())
            self.assertTrue(item["howToValidate"].strip())
            self.assertIsInstance(item["sourceIds"], list)


if __name__ == "__main__":
    unittest.main()
