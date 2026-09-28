import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reportlab.platypus import Paragraph, Table
from reportlab.platypus.flowables import KeepTogether

from agent import pdf_exporter
from agent.pdf_exporter import build_story, generate_dossier_pdf


def _texts(flowables) -> list[str]:
    """Every paragraph's text in reading order, walking into cards/tables."""
    out = []
    for f in flowables:
        if isinstance(f, Paragraph):
            out.append(f.getPlainText())
        elif isinstance(f, KeepTogether):
            out += _texts(f._content)
        elif isinstance(f, Table):
            for row in f._cellvalues:
                for cell in row:
                    out += _texts(cell if isinstance(cell, (list, tuple)) else [cell])
    return out


def _charts(flowables) -> list:
    """Every chart flowable in the story, walking into cards/tables."""
    out = []
    for f in flowables:
        if isinstance(f, (pdf_exporter._HBarChart, pdf_exporter._RadarChart,
                          pdf_exporter._MatrixChart, pdf_exporter._TimelineChart)):
            out.append(f)
        elif isinstance(f, KeepTogether):
            out += _charts(f._content)
        elif isinstance(f, Table):
            for row in f._cellvalues:
                for cell in row:
                    out += _charts(cell if isinstance(cell, (list, tuple)) else [cell])
    return out


CHARTED = {
    "confidence": {
        "percentage": 62, "label": "8/12 sources agree",
        "sourceCoverage": {"percentage": 78}, "crossSourceAgreement": {"percentage": 41},
        "directEvidenceRatio": {"percentage": 55}, "averageRelevance": 0.71,
        "sourceRecency": {"totalSources": 12, "sourcesWithKnownDate": 5},
    },
    "competitors": {"competitors": [
        {"name": "Waitwhile", "estimatedPrice": "mid", "featureBreadth": "broad"},
        {"name": "Qless", "estimatedPrice": "unknown", "featureBreadth": "broad"},
    ]},
    "swot": {"risks": [
        {"risk": "Churn", "severity": "high", "likelihood": "medium"},
        {"risk": "Cost", "severity": "low", "likelihood": "high"},
    ]},
    "marketOpportunity": {"viabilityIndex": {"dimensions": [
        {"name": "Demand", "score": 4}, {"name": "Competition", "score": 2}, {"name": "Pricing", "score": "n/a"},
        {"name": "Access", "score": 3},
    ]}},
    "mvp": {"deliveryRoadmap": {"phases": [
        {"phaseName": "Discovery", "durationWeeks": 2}, {"phaseName": "Build", "durationWeeks": 4},
    ]}},
}


FULL = {
    "idea": "QueueLess is a virtual queue for small clinics. Customers join from their phone.",
    "targetCustomer": "Small clinics",
    "summary": "Found 12 relevant sources [src-1].",
    "results": [{}] * 12,
    "verdict": {
        "decision": "validate_first", "label": "Validate first", "headline": "Promising, but prove it.",
        "score": 49, "scoreName": "Market viability",
        "reasons": ["Market viability is 49/100.", "Demand is fragmented."],
        "nextStep": "Run the top experiment.",
    },
    "marketOpportunity": {
        "opportunityScore": 52, "marketSize": "$0.9B [src-3]", "cagr": "11%",
        "segments": [{"segment": "Clinics", "painPoints": "Crowded rooms"}],
    },
    "competitors": {"competitors": [{"name": "Waitwhile", "priceBucket": "mid", "featureBreadth": "broad"}]},
    "whiteSpace": {"opportunities": [1, 2]},
    "swot": {
        "strengths": [{"text": "No app install"}], "weaknesses": [{"text": "Low switching cost"}],
        "opportunities": [{"text": "Contactless demand"}], "threats": [{"text": "Free bundled queues"}],
        "risks": [{"risk": "Churn after trial", "severity": "high", "likelihood": "medium", "mitigation": "Onboarding call"}],
    },
    "gtm": {"commercialModel": {"unitEconomics": {"estimatedCac": "$120"}, "pricingTiers": [{"tierName": "Pro", "price": "$29"}]}},
}


class PdfLayoutTests(unittest.TestCase):
    def test_verdict_first_then_summary_stats_then_numbered_sections(self):
        texts = _texts(build_story(FULL, "26 Sep 2026"))
        joined = "\n".join(texts)

        def at(needle):
            self.assertIn(needle, joined)
            return joined.index(needle)

        self.assertLess(at("Idea context".upper()), at("Validate first".upper()))
        self.assertLess(at("Validate first".upper()), at("EXECUTIVE SUMMARY"))
        self.assertLess(at("EXECUTIVE SUMMARY"), at("SOURCES"))
        self.assertLess(at("SOURCES"), at("§01"))
        self.assertLess(at("§01"), at("§02"))
        self.assertIn("MARKET SIZE & GROWTH", joined)
        self.assertIn("COMMERCIAL ECONOMICS", joined)

    def test_score_restating_reason_is_dropped_and_citation_markers_stripped(self):
        texts = _texts(build_story(FULL, "26 Sep 2026"))
        self.assertNotIn("Market viability is 49/100.", texts)
        self.assertIn("Demand is fragmented.", texts)
        self.assertIn("Found 12 relevant sources.", texts)
        self.assertIn("$0.9B", texts)
        # Secondary metric sits in the market section, labelled as such.
        self.assertIn("OPPORTUNITY SCORE (SECONDARY)", texts)

    def test_full_swot_and_risks_are_rendered(self):
        joined = "\n".join(_texts(build_story(FULL, "26 Sep 2026")))
        for text in ("No app install", "Low switching cost", "Contactless demand", "Free bundled queues",
                     "Churn after trial", "Onboarding call"):
            self.assertIn(text, joined)

    def test_legacy_session_without_verdict_uses_opportunity_score_as_headline(self):
        texts = _texts(build_story({"idea": "x", "marketOpportunity": {"opportunityScore": 60}}, "26 Sep 2026"))
        self.assertIn("FEASIBILITY OPPORTUNITY SCORE", "\n".join(texts))
        # Not repeated as a secondary tile.
        self.assertNotIn("OPPORTUNITY SCORE (SECONDARY)", texts)
        # No sources: no KPI strip.
        self.assertNotIn("SOURCES", texts)

    def test_model_text_is_escaped(self):
        data = {**FULL, "idea": "Tool for <b>founders</b> & teams", "summary": "A <script> & B"}
        texts = _texts(build_story(data, "26 Sep 2026"))
        self.assertIn("A <script> & B", texts)
        self.assertTrue(generate_dossier_pdf(data).startswith(b"%PDF"))

    def test_brand_fonts_are_embedded(self):
        pdf = generate_dossier_pdf(FULL)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"Fraunces", pdf)
        self.assertIn(b"Inter", pdf)

    def test_empty_payload_still_renders(self):
        self.assertTrue(generate_dossier_pdf({}).startswith(b"%PDF"))

    def test_charts_are_drawn_from_report_data(self):
        charts = _charts(build_story(CHARTED, "28 Sep 2026"))
        by_type = {type(c).__name__: c for c in charts}
        self.assertEqual(len(by_type["_HBarChart"].rows), 5)
        self.assertAlmostEqual(by_type["_HBarChart"].rows[3][1], 71.0)
        # The unscorable axis is skipped; three remain, enough for a radar.
        self.assertEqual([a[0] for a in by_type["_RadarChart"].axes], ["Demand", "Competition", "Access"])
        self.assertEqual(by_type["_TimelineChart"].phases, [("Discovery", 1, 2), ("Build", 3, 6)])
        matrices = [c for c in charts if isinstance(c, pdf_exporter._MatrixChart)]
        self.assertEqual(matrices[0].cells, {("mid", "broad"): ["Waitwhile"]})
        self.assertEqual(matrices[1].cells, {("high", "medium"): ["R1"], ("low", "high"): ["R2"]})
        self.assertTrue(generate_dossier_pdf(CHARTED).startswith(b"%PDF"))

    def test_charts_are_skipped_without_data(self):
        self.assertEqual(_charts(build_story({}, "28 Sep 2026")), [])

    def test_long_idea_is_shortened_for_the_title_only(self):
        idea = "A" * 200 + ". Second sentence."
        self.assertTrue(pdf_exporter._concept_title(idea).endswith("…"))
        self.assertLessEqual(len(pdf_exporter._concept_title(idea)), 90)
        self.assertIn(idea, _texts(build_story({"idea": idea}, "26 Sep 2026")))


if __name__ == "__main__":
    unittest.main()
