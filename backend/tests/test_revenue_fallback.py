import unittest
from unittest.mock import patch

from agent.llm import NeedsDeepAnalysisError
from agent.revenue_agent import _fallback_models, analyze_revenue_models

SOURCES = [{"title": "t", "url": "https://a.example/x", "snippet": "s", "angle": "Competitors"}]


def rival(name, pricing="unknown", model="unknown", ids=("src-1",)):
    return {"name": name, "pricing": pricing, "businessModel": model, "sourceIds": list(ids)}


class FallbackModelsTests(unittest.TestCase):
    def test_groups_rivals_by_how_they_describe_charging(self):
        competitors = {"competitors": [
            rival("Alpha", "$29 per month per seat", "SaaS subscription"),
            rival("Beta", "$49/mo", "Subscription with annual plans"),
            rival("Gamma", "Free tier, paid plans from $10", "Freemium"),
        ]}
        models = _fallback_models(competitors, {"src-1"})
        names = [m["name"] for m in models]
        self.assertEqual(names[0], "Subscription")
        self.assertIn("Freemium", names)
        self.assertEqual(models[0]["fit"], "high")
        self.assertEqual(models[0]["exampleCompanies"][:2], ["Alpha", "Beta"])
        self.assertTrue(all(m["inferred"] for m in models))

    def test_a_single_rival_gives_medium_fit(self):
        models = _fallback_models({"competitors": [rival("Solo", "$5 per call", "Usage based billing")]}, {"src-1"})
        self.assertEqual(models[0]["name"], "Usage-based")
        self.assertEqual(models[0]["fit"], "medium")

    def test_invents_nothing_when_rivals_have_no_pricing_text(self):
        competitors = {"competitors": [rival("Alpha"), rival("Beta")]}
        self.assertEqual(_fallback_models(competitors, {"src-1"}), [])
        self.assertEqual(_fallback_models(None, set()), [])

    def test_caps_at_three_and_drops_unknown_source_ids(self):
        competitors = {"competitors": [
            rival("A", "subscription", ids=("src-1", "src-99")),
            rival("B", "freemium"),
            rival("C", "pay as you go"),
            rival("D", "commission fee"),
        ]}
        models = _fallback_models(competitors, {"src-1"})
        self.assertLessEqual(len(models), 3)
        for m in models:
            self.assertTrue(set(m["sourceIds"]) <= {"src-1"})


class AnalyzeFallbackTests(unittest.TestCase):
    @patch("agent.revenue_agent.kickoff_with_fallback", side_effect=RuntimeError("quota"))
    def test_uses_competitor_pricing_instead_of_an_empty_section(self, _):
        competitors = {"competitors": [rival("Alpha", "$29 per month", "SaaS subscription")]}
        out = analyze_revenue_models("idea", "customers", None, competitors, SOURCES, allow_local=False)
        self.assertTrue(out["degraded"])
        self.assertEqual(out["models"][0]["name"], "Subscription")

    @patch("agent.revenue_agent.kickoff_with_fallback", side_effect=RuntimeError("quota"))
    def test_still_asks_for_deep_analysis_when_there_is_nothing_to_infer_from(self, _):
        with self.assertRaises(NeedsDeepAnalysisError):
            analyze_revenue_models("idea", "customers", None, {"competitors": []}, SOURCES, allow_local=False)

    @patch("agent.revenue_agent.kickoff_with_fallback", side_effect=RuntimeError("quota"))
    def test_returns_empty_degraded_when_local_allowed_and_nothing_to_infer(self, _):
        out = analyze_revenue_models("idea", "customers", None, {"competitors": []}, SOURCES, allow_local=True)
        self.assertEqual(out, {"models": [], "degraded": True})


if __name__ == "__main__":
    unittest.main()
