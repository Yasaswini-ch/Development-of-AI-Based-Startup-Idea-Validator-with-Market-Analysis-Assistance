"""The PDF prints what the on-screen report shows: comparison table, market tiers
and trends, competitor profiles, bear case, per-angle charts, every source, and a
note wherever a section used a fallback."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reportlab.platypus import Paragraph, Table
from reportlab.platypus.flowables import KeepTogether

from agent import pdf_exporter
from agent.pdf_exporter import build_story, generate_dossier_pdf


def _texts(flowables) -> list[str]:
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


def _all_text(data) -> str:
    return "\n".join(_texts(build_story(data, "2 Oct 2026")))


def _rival(name, cls="direct", **extra):
    base = {"name": name, "classification": cls, "offering": f"{name} offers time tracking and invoicing.",
            "pricing": "$12/mo", "businessModel": "subscription", "strengths": ["Simple timers"], "weaknesses": ["No reminders"],
            "gap": "Chase late payments automatically.", "estimatedPrice": "mid", "featureBreadth": "broad"}
    base.update(extra)
    return base


def _rich():
    results = [{"title": f"Source {i}", "url": f"https://example.com/{i}", "snippet": f"Excerpt number {i} about invoicing.",
                "angle": "Competitors" if i % 2 else "Market size & trends", "score": 0.8, "publishedAt": "2026-05-01"} for i in range(1, 31)]
    matrix = [{"dimension": d, "idea": "Idea answer", "competitors": {n: f"{n} {d}" for n in ("Harvest", "FreshBooks", "Clockify", "Toggl")}}
              for d in ("Price", "Core feature", "Target user")]
    return {
        "idea": "A freelancer invoicing app", "targetCustomer": "Freelancers", "problem": "Late payments",
        "results": results,
        "marketOpportunity": {
            "marketSize": "A growing market.",
            "tam": {"text": "$6 billion", "sourceIds": ["src-1"]},
            "sam": {"text": "About $490 million (estimate)", "sourceIds": [], "estimated": True, "assumptions": "Assumes 8% is reachable."},
            "som": {"text": "About $10 million (estimate)", "sourceIds": [], "estimated": True, "assumptions": "Assumes 2% is winnable."},
            "trends": [{"text": "Reminders are becoming standard", "sourceIds": ["src-1"]}],
            "segments": [{"segment": "Solo freelancers", "painPoints": "Chasing invoices", "motivations": "Get paid faster",
                          "buyingBehavior": "Prefer low monthly plans"}],
        },
        "competitors": {
            "competitors": [_rival("Harvest", enrichment={"source": "itunes", "averageRating": 4.5, "ratingCount": 1200}),
                            _rival("FreshBooks", enrichment={"source": "wikidata", "foundedYear": 2003}), _rival("Clockify"), _rival("Toggl", "indirect")],
            "comparisonMatrix": matrix, "profiled": True,
            "similarProducts": [{"name": "Bonsai", "tagline": "Freelance toolkit", "votesCount": 1204}],
        },
        "swot": {
            "strengths": [{"text": "Automation", "sourceIds": ["src-1"]}], "weaknesses": [], "opportunities": [],
            "threats": [{"text": "Incumbents add reminders", "sourceIds": []}],
            "risks": [{"risk": "Free tools are almost enough", "severity": "high", "likelihood": "medium", "mitigation": "Charge for automation only."}],
        },
        "confidence": {"percentage": 70, "label": "x", "sourceCoverage": {"percentage": 60},
                       "perAngle": {"Competitors": {"agreeingSources": 3, "totalSources": 6, "percentage": 50}}},
        "errors": {},
    }


class _Case(unittest.TestCase):
    def assertHas(self, needle, text):
        self.assertIn(needle.lower(), text.lower())

    def assertNotHas(self, needle, text):
        self.assertNotIn(needle.lower(), text.lower())


class FullReportContentTests(_Case):
    def setUp(self):
        self.text = _all_text(_rich())

    def test_market_tiers_are_labelled_sourced_or_estimate_with_their_assumption(self):
        for expected in ("TAM", "SAM", "SOM", "SOURCED", "ESTIMATE", "Assumes 8% is reachable.", "Not from a source."):
            self.assertHas(expected, self.text)

    def test_market_trends_and_the_full_segment_columns_are_printed(self):
        for expected in ("Market trends", "Reminders are becoming standard", "Motivations", "Buying behaviour", "Prefer low monthly plans"):
            self.assertHas(expected, self.text)

    def test_every_competitor_gets_a_profile_with_its_real_data(self):
        for expected in ("Competitor profiles", "Harvest", "4.5/5 from 1,200 ratings", "founded 2003", "STRENGTHS", "WEAKNESSES",
                         "WHERE YOUR IDEA CAN DIFFER", "Chase late payments automatically."):
            self.assertHas(expected, self.text)

    def test_the_comparison_matrix_is_printed_in_groups_of_three_rivals(self):
        self.assertHas("How your idea compares", self.text)
        self.assertHas("Harvest Core feature", self.text)  # a cell
        self.assertHas("Toggl Price", self.text)  # the fourth rival lands in a second table

    def test_similar_products_are_listed(self):
        self.assertHas("Bonsai", self.text)
        self.assertHas("1,204 votes", self.text)

    def test_the_bear_case_lists_objections_with_the_suggested_answer(self):
        for expected in ("Bear case", "OBJECTION #1", "HIGH SEVERITY", "Free tools are almost enough", "Your answer:", "Charge for automation only."):
            self.assertHas(expected, self.text)
        self.assertHas("Incumbents add reminders", self.text)  # threats fill the remaining slots

    def test_every_retrieved_source_is_in_the_evidence_log(self):
        self.assertHas("Evidence log", self.text)
        for i in (1, 15, 30):
            self.assertHas(f"Source {i}", self.text)
        self.assertHas("Excerpt number 30 about invoicing.", self.text)
        self.assertHas("80% relevant", self.text)

    def test_the_per_angle_charts_are_present(self):
        charts = [f for f in _flatten(build_story(_rich(), "x")) if isinstance(f, pdf_exporter._HBarChart)]
        self.assertGreaterEqual(len(charts), 3)  # evidence confidence, agreement by angle, sources by angle
        self.assertHas("Source agreement by research angle", self.text)
        self.assertHas("Sources by research angle", self.text)


def _flatten(flowables):
    out = []
    for f in flowables:
        out.append(f)
        if isinstance(f, KeepTogether):
            out += _flatten(f._content)
        elif isinstance(f, Table):
            for row in f._cellvalues:
                for cell in row:
                    out += _flatten(cell if isinstance(cell, (list, tuple)) else [cell])
    return out


class ReportNotesTests(_Case):
    def test_a_fallback_section_is_called_out(self):
        data = _rich()
        data["swot"]["degraded"] = True
        data["marketOpportunity"]["degraded"] = True
        data["revenueModels"] = {"models": [{"name": "Subscription", "fit": "high", "rationale": "x", "tradeoffs": "y"}], "degraded": True}
        text = _all_text(data)
        self.assertHas("About this report", text)
        for label in ("SWOT and risk", "Market analysis", "Revenue models"):
            self.assertHas(f"{label}: built by a rule-based fallback", text)

    def test_unprofiled_competitors_and_section_errors_are_called_out(self):
        data = _rich()
        data["competitors"]["profiled"] = False
        data["errors"] = {"gtm": "This analysis hit a temporary usage limit."}
        text = _all_text(data)
        self.assertHas("profiles come from the search text only", text)
        self.assertHas("gtm: This analysis hit a temporary usage limit.", text)

    def test_estimates_are_explained(self):
        self.assertHas("SAM and SOM are estimates", _all_text(_rich()))

    def test_a_clean_report_has_no_notes_box(self):
        data = _rich()
        data["marketOpportunity"]["sam"] = {"text": "$1B", "sourceIds": ["src-1"]}
        data["marketOpportunity"]["som"] = None
        self.assertNotHas("About this report", _all_text(data))


class RobustnessTests(_Case):
    def test_an_empty_report_still_builds(self):
        self.assertTrue(generate_dossier_pdf({}).startswith(b"%PDF"))

    def test_the_rich_report_produces_a_pdf(self):
        self.assertTrue(generate_dossier_pdf(_rich()).startswith(b"%PDF"))

    def test_awkward_values_do_not_break_it(self):
        data = _rich()
        data["competitors"]["competitors"].append({"name": "Odd & <Co>", "classification": None, "strengths": [None, "", 5], "weaknesses": "text",
                                                    "enrichment": {"averageRating": "n/a", "ratingCount": None}})
        data["competitors"]["comparisonMatrix"].append({"dimension": "X" * 400, "idea": "Y" * 900, "competitors": {"Harvest": "Z" * 900, "Ghost": "?"}})
        data["marketOpportunity"]["trends"] = [None, "plain string", {"text": ""}]
        data["marketOpportunity"]["tam"] = {"text": "T" * 3000, "sourceIds": None}
        data["results"].append({"title": None, "url": "https://example.com/" + "a" * 300, "snippet": None, "score": "high", "publishedAt": None})
        data["swot"]["risks"].append("a plain string risk")
        self.assertTrue(generate_dossier_pdf(data).startswith(b"%PDF"))

    def test_a_large_evidence_set_is_capped_and_says_so(self):
        data = _rich()
        data["results"] = [{"title": f"S{i}", "url": f"https://e.com/{i}", "snippet": "x", "angle": "A", "score": 0.5} for i in range(150)]
        text = _all_text(data)
        self.assertHas("All 150 sources", text)
        self.assertHas("30 further sources are not listed here.", text)

    def test_the_placeholder_gap_text_is_not_printed_as_a_finding(self):
        data = _rich()
        data["competitors"]["competitors"] = [_rival("Harvest", gap="Identified automatically from search results - a detailed, idea-specific comparison wasn't generated for this request.")]
        data["competitors"]["comparisonMatrix"] = []
        self.assertNotHas("wasn't generated", _all_text(data))


if __name__ == "__main__":
    unittest.main()


class BrandLogoTests(unittest.TestCase):
    def test_logo_asset_ships_and_the_pdf_still_builds_with_and_without_it(self):
        from unittest.mock import patch

        from agent import pdf_exporter

        self.assertTrue(os.path.exists(pdf_exporter._LOGO_PATH))
        data = {"idea": "x", "targetCustomer": "y"}
        with_logo = pdf_exporter.generate_dossier_pdf(data)
        with patch.object(pdf_exporter, "_LOGO_PATH", "missing.png"):
            without = pdf_exporter.generate_dossier_pdf(data)
        self.assertTrue(with_logo.startswith(b"%PDF") and without.startswith(b"%PDF"))
        self.assertGreater(len(with_logo), len(without))
