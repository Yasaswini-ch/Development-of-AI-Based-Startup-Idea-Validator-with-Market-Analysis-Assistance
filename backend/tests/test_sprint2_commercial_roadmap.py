"""Contract tests for Sprint 2 of the 5-pillar spec: Pillar 5A (GTM
Commercial Architecture / unit economics + pricing tiers) and Pillar 5B
(Stage-Gated MVP Delivery Roadmap).

Standalone like test_viability_score.py: only imports the pure modules
(no fastapi/langgraph/crewai needed).
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.commercial_model import build_commercial_model
from agent.delivery_roadmap import build_delivery_roadmap

_UNIT_ECON_KEYS = {"estimatedCac", "targetArpu", "paybackHorizonMonths", "ltvToCacRatio", "economicRationale"}
_TIER_KEYS = {"tierName", "price", "billingCycle", "targetSegment", "includedFeatures"}

_HIGH_FIT_CHANNELS = [{"text": "Developer communities", "fitScore": "high", "sourceIds": []}]
_LOW_FIT_CHANNELS = [{"text": "Paid national TV", "fitScore": "low", "sourceIds": []}]

_LOW_RISK_SWOT = {"risks": [{"risk": "Minor onboarding friction", "severity": "low", "likelihood": "low"}]}
_HIGH_RISK_SWOT = {"risks": [{"risk": "Regulatory exposure", "severity": "high", "likelihood": "high"}]}


class CommercialModelTests(unittest.TestCase):
    def test_matches_the_unit_economics_and_pricing_contract(self):
        model = build_commercial_model("A SaaS app for freelancers")
        self.assertEqual(set(model["unitEconomics"]), _UNIT_ECON_KEYS)
        self.assertEqual(len(model["pricingTiers"]), 3)
        for tier in model["pricingTiers"]:
            self.assertEqual(set(tier), _TIER_KEYS)

    def test_starter_tier_is_always_free(self):
        model = build_commercial_model("A hardware wearable for fitness")
        starter = model["pricingTiers"][0]
        self.assertEqual(starter["tierName"], "Starter")
        self.assertEqual(starter["price"], "$0")

    def test_pricing_tiers_strictly_increase(self):
        model = build_commercial_model("A SaaS tool for invoicing")
        prices = [int(t["price"].lstrip("$")) for t in model["pricingTiers"]]
        self.assertEqual(prices, sorted(prices))
        self.assertLess(prices[0], prices[1])
        self.assertLess(prices[1], prices[2])

    def test_capital_heavy_idea_prices_higher_than_software_idea(self):
        software = build_commercial_model("An AI-powered invoicing app")
        hardware = build_commercial_model("A hardware wearable manufacturing device")
        software_arpu = int(software["unitEconomics"]["targetArpu"].split("$")[1].split("/")[0])
        hardware_arpu = int(hardware["unitEconomics"]["targetArpu"].split("$")[1].split("/")[0])
        self.assertGreater(hardware_arpu, software_arpu)

    def test_competitor_pricing_signal_overrides_idea_wording(self):
        competitors_low = {"competitors": [{"name": "A", "estimatedPrice": "low"}, {"name": "B", "estimatedPrice": "low"}]}
        model = build_commercial_model("An enterprise B2B platform", competitors_data=competitors_low)
        arpu = int(model["unitEconomics"]["targetArpu"].split("$")[1].split("/")[0])
        self.assertEqual(arpu, 19)

    def test_high_fit_channels_produce_lower_cac_than_low_fit(self):
        high_fit = build_commercial_model("A SaaS tool", channels=_HIGH_FIT_CHANNELS)
        low_fit = build_commercial_model("A SaaS tool", channels=_LOW_FIT_CHANNELS)

        def cac_low(model):
            return int(model["unitEconomics"]["estimatedCac"].split("$")[1].split(" ")[0])

        self.assertLess(cac_low(high_fit), cac_low(low_fit))

    def test_higher_execution_risk_lowers_ltv_to_cac_ratio(self):
        low_risk = build_commercial_model("A SaaS tool", swot_data=_LOW_RISK_SWOT)
        high_risk = build_commercial_model("A SaaS tool", swot_data=_HIGH_RISK_SWOT)

        def ratio(model):
            return float(model["unitEconomics"]["ltvToCacRatio"].rstrip("x"))

        self.assertGreater(ratio(low_risk), ratio(high_risk))

    def test_empty_inputs_degrade_gracefully(self):
        model = build_commercial_model("")
        self.assertEqual(set(model["unitEconomics"]), _UNIT_ECON_KEYS)
        self.assertEqual(len(model["pricingTiers"]), 3)


_MVP_DATA = {
    "features": [
        {"feature": "Split-payout links", "rationale": "x", "impact": "high", "effort": "medium", "sourceIds": []},
        {"feature": "Stripe Connect onboarding", "rationale": "x", "impact": "high", "effort": "high", "sourceIds": []},
    ],
    "niceToHave": [
        {"feature": "Multi-currency support", "rationale": "x", "sourceIds": []},
    ],
    "deferred": [],
}


class DeliveryRoadmapTests(unittest.TestCase):
    def test_matches_the_roadmap_contract(self):
        roadmap = build_delivery_roadmap(_MVP_DATA)
        self.assertIn("totalTimelineWeeks", roadmap)
        self.assertIn("teamComposition", roadmap)
        self.assertEqual(len(roadmap["phases"]), 3)
        for phase in roadmap["phases"]:
            self.assertIn("phaseName", phase)
            self.assertIn("durationWeeks", phase)
            self.assertIsInstance(phase["coreDeliverables"], list)
            self.assertTrue(phase["coreDeliverables"])
            self.assertIsInstance(phase["exitGateMilestones"], list)
            self.assertTrue(phase["exitGateMilestones"])

    def test_phase_names_are_alpha_beta_ga_in_order(self):
        names = [p["phaseName"] for p in build_delivery_roadmap(_MVP_DATA)["phases"]]
        self.assertIn("Alpha", names[0])
        self.assertIn("Beta", names[1])
        self.assertIn("GA", names[2])

    def test_phase_1_deliverables_come_from_the_actual_mvp_features(self):
        phase1 = build_delivery_roadmap(_MVP_DATA)["phases"][0]
        self.assertIn("Split-payout links", phase1["coreDeliverables"])
        self.assertIn("Stripe Connect onboarding", phase1["coreDeliverables"])

    def test_total_timeline_is_sum_of_phase_durations(self):
        roadmap = build_delivery_roadmap(_MVP_DATA)
        self.assertEqual(roadmap["totalTimelineWeeks"], sum(p["durationWeeks"] for p in roadmap["phases"]))

    def test_more_high_effort_features_take_longer_than_fewer_low_effort_ones(self):
        heavy = {"features": [{"feature": f"F{i}", "effort": "high", "impact": "high"} for i in range(5)]}
        light = {"features": [{"feature": "F1", "effort": "low", "impact": "low"}]}
        self.assertGreater(
            build_delivery_roadmap(heavy)["phases"][0]["durationWeeks"],
            build_delivery_roadmap(light)["phases"][0]["durationWeeks"],
        )

    def test_team_composition_has_fte_allocations(self):
        roadmap = build_delivery_roadmap(_MVP_DATA)
        self.assertTrue(roadmap["teamComposition"])
        for member in roadmap["teamComposition"]:
            self.assertIn("role", member)
            self.assertIn("allocation", member)
            self.assertIn("FTE", member["allocation"])

    def test_empty_mvp_data_degrades_gracefully(self):
        roadmap = build_delivery_roadmap(None)
        self.assertEqual(len(roadmap["phases"]), 3)
        self.assertGreater(roadmap["totalTimelineWeeks"], 0)


if __name__ == "__main__":
    unittest.main()
