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

    def test_cagr_is_parsed_from_market_size_prose_when_no_structured_field(self):
        # market_agent.py has never produced a structured "cagr" field - the
        # model states it (when a source has one) inside marketSize's prose.
        market_opp = {"marketSize": "Market projected $446 million in 2025 with 5.3% CAGR to 2033."}
        texts = _texts(build_story({"idea": "x", "marketOpportunity": market_opp}, "29 Sep 2026"))
        self.assertIn("5.3% CAGR", texts)
        self.assertNotIn("N/A", texts)

    def test_cagr_falls_back_to_na_when_not_stated(self):
        texts = _texts(build_story({"idea": "x", "marketOpportunity": {"marketSize": "Emerging, no figures cited."}}, "29 Sep 2026"))
        self.assertIn("N/A", texts)

    def test_cagr_prefers_a_structured_field_if_ever_present(self):
        market_opp = {"marketSize": "Text says 9% CAGR.", "cagr": "12% (structured)"}
        texts = _texts(build_story({"idea": "x", "marketOpportunity": market_opp}, "29 Sep 2026"))
        self.assertIn("12% (structured)", texts)

    def test_competitor_classification_always_shown_even_when_not_llm_profiled(self):
        # Regression: the table used to hide the Type column entirely
        # whenever competitors["profiled"] was False (LLM discovery
        # failed/skipped), even for NER-only rows that do carry a
        # classification. Every row should now show Direct/Indirect/Unclear.
        data = {"idea": "x", "competitors": {"profiled": False, "competitors": [
            {"name": "PayPal", "classification": "direct", "estimatedPrice": "mid", "featureBreadth": "narrow",
             "weaknesses": ["Fees erode thin margins."]},
            {"name": "Finboo", "classification": "unknown", "estimatedPrice": "unknown", "featureBreadth": "narrow"},
        ]}}
        texts = _texts(build_story(data, "29 Sep 2026"))
        self.assertIn("Direct rival", texts)
        self.assertIn("Unclear", texts)
        self.assertTrue(any("Fees erode thin margins." in text for text in texts))

    def test_competitor_table_cells_are_capped_to_one_short_line(self):
        # Regression: a free-text "pricing" note or long name wrapping to
        # multiple lines in a table cell puts that cell's continuation
        # line at a different y-position than its single-line row
        # neighbours - several PDF viewers reconstruct copy/paste order
        # from glyph position, not draw order, so a wrapped row can scramble
        # which values later rows' text gets grouped with (confirmed from
        # a user's pasted copy: values interleaved across unrelated rows).
        # Every field here is long enough to wrap at the table's real
        # column widths if the exporter didn't cap it to one line first.
        data = {"idea": "x", "competitors": {"competitors": [
            {"name": "A Very Long Competitor Name That Would Definitely Wrap", "classification": "direct",
             "pricing": "Enterprise pricing available on request, billed annually with a long-term contract",
             "featureBreadth": "narrow"},
        ]}}
        story = build_story(data, "29 Sep 2026")
        cell_paragraphs = [p for f in story if isinstance(f, Table) for row in f._cellvalues for cell in row
                           for p in (cell if isinstance(cell, (list, tuple)) else [cell]) if isinstance(p, Paragraph)]
        name_cell = next(p for p in cell_paragraphs if "Very Long Competitor" in p.getPlainText())
        pricing_cell = next(p for p in cell_paragraphs if "Enterprise pricing" in p.getPlainText())
        # The competitor table's real column widths (pdf_exporter._competitors),
        # minus each cell's 8pt+8pt padding - the usable text width the cap
        # has to fit inside.
        name_width = (pdf_exporter.CONTENT_W - 340) - 16
        pricing_width = 130 - 16
        for p, width in ((name_cell, name_width), (pricing_cell, pricing_width)):
            self.assertTrue(p.getPlainText().endswith("…"))
            p.wrap(width, 100)
            self.assertEqual(len(p.blPara.lines), 1)

    def test_gtm_strategy_section_renders_positioning_channels_and_approach(self):
        gtm = {"positioning": "The affordable alternative.",
               "channels": [{"text": "Freelancer subreddits", "fitScore": "high", "tactics": ["Post weekly"]}],
               "earlyCustomerApproach": "White-glove onboarding for the first 20 users."}
        texts = _texts(build_story({"idea": "x", "gtm": gtm}, "29 Sep 2026"))
        for expected in ("GO-TO-MARKET STRATEGY", "The affordable alternative.", "Freelancer subreddits",
                         "Post weekly", "White-glove onboarding for the first 20 users."):
            self.assertIn(expected, texts)

    def test_revenue_models_section_renders_each_model(self):
        revenue_models = {"models": [
            {"name": "Subscription (SaaS)", "fit": "high", "rationale": "Recurring billing fits the use case.",
             "tradeoffs": "Freemium cannibalizes conversion.", "pricingRange": "$0-$60/mo", "exampleCompanies": ["FreshBooks"]},
        ]}
        texts = _texts(build_story({"idea": "x", "revenueModels": revenue_models}, "29 Sep 2026"))
        joined = "\n".join(texts)
        for expected in ("REVENUE MODEL OPTIONS", "Subscription (SaaS)", "Recurring billing fits the use case.",
                         "Freemium cannibalizes conversion.", "FreshBooks"):
            self.assertIn(expected, joined)

    def test_gtm_and_revenue_sections_skipped_without_data(self):
        texts = _texts(build_story({"idea": "x"}, "29 Sep 2026"))
        self.assertNotIn("GO-TO-MARKET STRATEGY", texts)
        self.assertNotIn("REVENUE MODEL OPTIONS", texts)

    def test_newly_covered_sections_render_their_data(self):
        # Regression: assumptions, experiments, action plan, contradictions,
        # mvp features, white-space opportunities and cited sources were
        # all real pipeline outputs the PDF simply never read.
        data = {
            "idea": "x",
            "mvp": {"features": [{"feature": "AI time tracking", "rationale": "Removes the #1 chore.",
                                   "impact": "high", "effort": "medium"}],
                    "niceToHave": [{"feature": "Mobile app", "rationale": "Nice but not core."}]},
            "whiteSpace": {"competitionNote": "3 named competitors were identified.",
                           "opportunities": [{"title": "Serve solo freelancers", "why": "Manual admin eats hours.",
                                              "fit": "Wants to get paid faster."}]},
            "assumptions": {"assumptions": [{"assumption": "Freelancers will pay $19/mo", "category": "demand",
                                              "uncertainty": "high", "howToValidate": "Run a landing page test.",
                                              "riskIfWrong": "CAC never pays back.", "timeToValidate": "2 weeks"}]},
            "experiments": [{"hypothesis": "Freelancers feel this pain strongly enough to pay.",
                              "method": "Landing page smoke test.", "successMetric": "20% signup rate.",
                              "duration": "14 days", "budget": "low"}],
            "contradictions": [{"type": "marketGrowthVsWeakDemand",
                                 "summary": "Market described as growing, but demand evidence reads weak."}],
            "actionPlan": {"next7Days": {"title": "Test the highest-risk assumptions",
                                          "items": [{"text": "Validate the payment-integration risk."}]},
                           "next30Days": {"title": "Build the smallest useful MVP", "items": []},
                           "next90Days": {"title": "Execute GTM channels", "items": []}},
            "sources": [{"sourceId": "src-1", "title": "Freelancer invoicing market report",
                         "url": "https://example.com/report", "angle": "Market size & trends"}],
            "results": [{}] * 20,
        }
        texts = _texts(build_story(data, "29 Sep 2026"))
        joined = "\n".join(texts)
        for expected in (
            "MVP FEATURE PLAN", "AI time tracking", "Mobile app",
            "MARKET WHITE SPACE", "Serve solo freelancers", "Wants to get paid faster.",
            "KEY ASSUMPTIONS TO VALIDATE", "Freelancers will pay $19/mo", "Run a landing page test.",
            "VALIDATION EXPERIMENTS", "Landing page smoke test.",
            "TENSION FLAGS", "Market described as growing, but demand evidence reads weak.",
            "90-DAY ACTION PLAN", "Validate the payment-integration risk.",
            "CITED SOURCES", "Freelancer invoicing market report",
        ):
            self.assertIn(expected, joined)
        # 20 results retrieved, only 1 cited - the remainder note should show.
        self.assertIn("20 sources were retrieved in total", joined)

    def test_newly_covered_sections_skipped_without_data(self):
        texts = _texts(build_story({"idea": "x"}, "29 Sep 2026"))
        for absent in ("MVP FEATURE PLAN", "MARKET WHITE SPACE", "KEY ASSUMPTIONS TO VALIDATE",
                       "VALIDATION EXPERIMENTS", "TENSION FLAGS", "90-DAY ACTION PLAN", "CITED SOURCES"):
            self.assertNotIn(absent, texts)


if __name__ == "__main__":
    unittest.main()
