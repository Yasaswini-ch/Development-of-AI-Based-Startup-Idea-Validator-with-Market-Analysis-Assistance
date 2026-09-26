"""Contract tests for Sprint 3 of the 5-pillar spec: Pillar 4 (5-Vector
Strategic Wedge Blueprint).

Standalone like test_viability_score.py: only imports the pure module
(no fastapi/langgraph/crewai needed).
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.strategic_wedge import build_strategic_wedges

_VECTOR_KEYS = {
    "observedFriction",
    "incumbentBlindspot",
    "structuralTailwind",
    "asymmetricWedge",
    "defensibilityMoat",
}
_BLUEPRINT_KEYS = {"opportunityTitle", "convictionPercent", "vectors", "keyRisk", "supportingSourceIds"}

_RESULTS = [
    {"url": "https://example.com/report", "snippet": "Market growing fast."},
    {"url": "https://acme.com", "snippet": "Acme is a rival product."},
]

_MARKET_GROUNDED = {
    "trends": [{"text": "The market is growing at 20% CAGR.", "sourceIds": ["src-1"]}],
    "segments": [
        {
            "segment": "Freelance collectives",
            "painPoints": "They lose hours reconciling multi-client payouts.",
            "motivations": "Want a single link to split payments instantly.",
            "buyingBehavior": "Try free tools first.",
            "sourceIds": ["src-1"],
        }
    ],
}

_MARKET_UNGROUNDED = {
    "trends": [],
    "segments": [
        {
            "segment": "Agencies",
            "painPoints": "",
            "motivations": "",
            "buyingBehavior": "",
            "sourceIds": [],
        }
    ],
}

_COMPETITORS_WITH_WEAKNESSES = {
    "competitors": [
        {"name": "Acme", "url": "https://acme.com", "weaknesses": ["Charges per seat", "No multi-party splits"]},
    ]
}

_COMPETITORS_EMPTY = {"competitors": []}


class StrategicWedgeTests(unittest.TestCase):
    def test_matches_the_blueprint_contract(self):
        result = build_strategic_wedges(_MARKET_GROUNDED, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)
        self.assertTrue(result["blueprints"])
        for blueprint in result["blueprints"]:
            self.assertEqual(set(blueprint), _BLUEPRINT_KEYS)
            self.assertEqual(set(blueprint["vectors"]), _VECTOR_KEYS)
            self.assertIsInstance(blueprint["supportingSourceIds"], list)

    def test_one_blueprint_per_segment_up_to_the_cap(self):
        market = {**_MARKET_GROUNDED, "segments": _MARKET_GROUNDED["segments"] * 5}
        result = build_strategic_wedges(market, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)
        self.assertEqual(len(result["blueprints"]), 3)

    def test_no_segments_returns_empty_blueprints(self):
        result = build_strategic_wedges({"segments": []}, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)
        self.assertEqual(result["blueprints"], [])

    def test_friction_and_wedge_come_from_the_real_segment_text(self):
        blueprint = build_strategic_wedges(_MARKET_GROUNDED, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)["blueprints"][0]
        self.assertIn("reconciling multi-client payouts", blueprint["vectors"]["observedFriction"])
        self.assertIn("split payments instantly", blueprint["vectors"]["asymmetricWedge"])

    def test_blindspot_cites_the_top_competitors_own_weaknesses(self):
        blueprint = build_strategic_wedges(_MARKET_GROUNDED, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)["blueprints"][0]
        self.assertIn("Charges per seat", blueprint["vectors"]["incumbentBlindspot"])
        self.assertIn("Acme", blueprint["vectors"]["incumbentBlindspot"])

    def test_conviction_is_higher_when_more_vectors_are_grounded(self):
        grounded = build_strategic_wedges(_MARKET_GROUNDED, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)["blueprints"][0]
        ungrounded = build_strategic_wedges(_MARKET_UNGROUNDED, _COMPETITORS_EMPTY, [])["blueprints"][0]
        self.assertGreater(grounded["convictionPercent"], ungrounded["convictionPercent"])

    def test_conviction_percent_is_always_0_to_100(self):
        for blueprint in build_strategic_wedges(_MARKET_GROUNDED, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)["blueprints"]:
            self.assertGreaterEqual(blueprint["convictionPercent"], 0)
            self.assertLessEqual(blueprint["convictionPercent"], 100)

    def test_supporting_source_ids_are_real_and_deduplicated(self):
        blueprint = build_strategic_wedges(_MARKET_GROUNDED, _COMPETITORS_WITH_WEAKNESSES, _RESULTS)["blueprints"][0]
        valid = {"src-1", "src-2"}
        self.assertTrue(set(blueprint["supportingSourceIds"]) <= valid)
        self.assertEqual(len(blueprint["supportingSourceIds"]), len(set(blueprint["supportingSourceIds"])))

    def test_more_competitors_changes_the_moat_wording(self):
        many_competitors = {"competitors": [{"name": f"C{i}"} for i in range(6)]}
        blueprint = build_strategic_wedges(_MARKET_GROUNDED, many_competitors, _RESULTS)["blueprints"][0]
        self.assertIn("6", blueprint["vectors"]["defensibilityMoat"])

    def test_empty_inputs_degrade_gracefully(self):
        result = build_strategic_wedges(None, None, None)
        self.assertEqual(result, {"blueprints": []})


if __name__ == "__main__":
    unittest.main()
