"""Backend fields added for the results-view UI review (docs/23):
commercialModel.basis (the "Based on" chips), verdict.scoreName (the
verdict card's headline score label), blueprint.segment (wedge card
titles), avatarUrl/authProvider on GET /auth/me (the account-menu avatar),
and the five-pillar sections in the PDF dossier.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete

import main
from agent.commercial_model import build_commercial_model
from agent.db import get_engine, users_table
from agent.pdf_exporter import generate_dossier_pdf
from agent.strategic_wedge import build_strategic_wedges
from agent.verdict import build_verdict


class CommercialModelBasisTests(unittest.TestCase):
    def test_basis_names_competitor_pricing_when_it_is_known(self):
        model = build_commercial_model(
            "A scheduling app",
            competitors_data={"competitors": [{"name": "A", "estimatedPrice": "low"}]},
            channels=[{"text": "SEO", "fitScore": "high"}, {"text": "Ads", "fitScore": "low"}],
            swot_data={"risks": [{"severity": "high", "likelihood": "high"}]},
        )
        self.assertEqual(
            model["basis"],
            {"priceTier": "low", "priceTierSource": "competitors", "channelCount": 2, "executionRiskPercent": 100},
        )

    def test_basis_falls_back_to_the_idea_wording(self):
        basis = build_commercial_model("A hardware sensor for farms")["basis"]
        self.assertEqual(basis["priceTier"], "high")
        self.assertEqual(basis["priceTierSource"], "idea")
        self.assertEqual(basis["channelCount"], 0)


class VerdictScoreNameTests(unittest.TestCase):
    def test_verdict_names_the_score_it_used(self):
        verdict = build_verdict({"opportunityScore": 50}, {"score": 72})
        self.assertEqual(verdict["score"], 72)
        self.assertEqual(verdict["scoreName"], "Market viability")

    def test_falls_back_to_opportunity_score_name(self):
        verdict = build_verdict({"opportunityScore": 50})
        self.assertEqual(verdict["scoreName"], "Opportunity score")


class WedgeSegmentTests(unittest.TestCase):
    def test_blueprint_carries_the_bare_segment_name(self):
        result = build_strategic_wedges({"segments": [{"segment": "Freelance designers", "painPoints": "x"}]}, {})
        self.assertEqual(result["blueprints"][0]["segment"], "Freelance designers")


class AuthMeProfileTests(unittest.TestCase):
    def setUp(self):
        with get_engine().begin() as conn:
            conn.execute(delete(users_table))
        main._clear_rate_limits()
        self.client = TestClient(main.app)

    def test_local_account_reports_local_provider_and_no_avatar(self):
        token = self.client.post(
            "/auth/signup", json={"email": "local@example.com", "password": "correct-horse-battery"}
        ).json()["token"]
        body = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(body["authProvider"], "local")
        self.assertIsNone(body["avatarUrl"])

    @patch(
        "agent.auth.verify_google_id_token",
        return_value={"sub": "1", "email": "g@example.com", "name": "G", "picture": "https://example.com/a.png"},
    )
    def test_google_account_reports_its_avatar(self, _verify):
        token = self.client.post("/auth/google", json={"idToken": "t"}).json()["token"]
        body = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(body["authProvider"], "google")
        self.assertEqual(body["avatarUrl"], "https://example.com/a.png")


class PdfFivePillarSectionTests(unittest.TestCase):
    def test_pdf_grows_with_five_pillar_sections_and_escapes_text(self):
        base = {"idea": "x", "marketOpportunity": {"opportunityScore": 60}}
        full = {
            **base,
            "marketOpportunity": {
                "opportunityScore": 60,
                "voiceOfMarket": [{"quote": "Doing this <by hand> & slowly is painful", "speakerOrSource": "Reddit thread"}],
                "viabilityIndex": {"dimensions": [{"name": "Demand Urgency", "score": 4, "rating": "High", "rationale": "r"}]},
            },
            "whiteSpace": {"blueprints": [{"segment": "Freelancers", "convictionPercent": 50, "vectors": {"asymmetricWedge": "w"}}]},
            "mvp": {"deliveryRoadmap": {"phases": [{"phaseName": "Alpha", "durationWeeks": 4, "coreDeliverables": ["a"], "exitGateMilestones": ["b"]}]}},
            "gtm": {"commercialModel": {"unitEconomics": {"estimatedCac": "$10"}, "pricingTiers": [{"tierName": "Pro", "price": "$45"}]}},
            "verdict": {"label": "Pursue", "headline": "h", "score": 70, "scoreName": "Market viability"},
        }
        base_pdf = generate_dossier_pdf(base)
        full_pdf = generate_dossier_pdf(full)
        self.assertTrue(full_pdf.startswith(b"%PDF"))
        self.assertGreater(len(full_pdf), len(base_pdf))


if __name__ == "__main__":
    unittest.main()


def test_extract_inline_citations_strips_markers_and_keeps_ids():
    from agent.structured_output import extract_inline_citations

    text, ids = extract_inline_citations(
        "The market was $5.9 billion in 2024 【src-1】【src-3】; it will reach $24.96 billion by 2029 [src-4, src-1]."
    )
    assert text == "The market was $5.9 billion in 2024; it will reach $24.96 billion by 2029."
    assert ids == ["src-1", "src-3", "src-4"]
    assert extract_inline_citations("Growing fast (2024).") == ("Growing fast (2024).", [])
