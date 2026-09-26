import unittest

from agent.verdict import build_verdict


class VerdictTests(unittest.TestCase):
    def test_no_market_opportunity_returns_none(self):
        self.assertIsNone(build_verdict(None))

    def test_strong_signals_with_no_risk_pursue(self):
        result = build_verdict(
            {"opportunityScore": 80},
            market_viability={"score": 78},
            swot={"risks": []},
            assumptions={"assumptions": []},
            confidence={"sourceCoverage": {"percentage": 80, "totalClaims": 10}},
        )
        self.assertEqual(result["decision"], "pursue")
        self.assertEqual(result["score"], 78)
        self.assertTrue(result["reasons"])
        self.assertTrue(result["nextStep"])

    def test_weak_score_or_many_high_risks_rethink(self):
        result = build_verdict(
            {"opportunityScore": 20},
            market_viability={"score": 25},
        )
        self.assertEqual(result["decision"], "rethink")

        risky = build_verdict(
            {"opportunityScore": 70},
            market_viability={"score": 70},
            swot={
                "risks": [
                    {"risk": "a", "severity": "high", "mitigation": "x"},
                    {"risk": "b", "severity": "high", "mitigation": "x"},
                    {"risk": "c", "severity": "high", "mitigation": "x"},
                ]
            },
        )
        self.assertEqual(risky["decision"], "rethink")

    def test_unmitigated_high_risk_forces_validate_first(self):
        result = build_verdict(
            {"opportunityScore": 80},
            market_viability={"score": 80},
            swot={"risks": [{"risk": "No moat", "severity": "high", "mitigation": ""}]},
        )
        self.assertEqual(result["decision"], "validate_first")
        self.assertIn("No moat", result["nextStep"])

    def test_unproven_assumption_becomes_next_step(self):
        result = build_verdict(
            {"opportunityScore": 80},
            market_viability={"score": 80},
            assumptions={
                "assumptions": [
                    {
                        "assumption": "Customers will pay monthly",
                        "uncertainty": "high",
                        "howToValidate": "Run a pricing survey",
                    }
                ]
            },
        )
        self.assertEqual(result["decision"], "validate_first")
        self.assertIn("Customers will pay monthly", result["nextStep"])
        self.assertIn("Run a pricing survey", result["nextStep"])

    def test_thin_evidence_downgrades_pursue(self):
        result = build_verdict(
            {"opportunityScore": 80},
            market_viability={"score": 80},
            confidence={"sourceCoverage": {"percentage": 10, "totalClaims": 10}},
        )
        self.assertEqual(result["decision"], "validate_first")

    def test_degraded_market_opportunity_is_never_pursue(self):
        result = build_verdict({"opportunityScore": 90, "degraded": True}, market_viability={"score": 90})
        self.assertEqual(result["decision"], "validate_first")
        self.assertTrue(any("reduced mode" in r for r in result["reasons"]))

    def test_falls_back_to_opportunity_score_without_viability(self):
        result = build_verdict({"opportunityScore": 45})
        self.assertEqual(result["score"], 45)


if __name__ == "__main__":
    unittest.main()
