import os
import unittest

os.environ.setdefault("WEB_CACHE", "0")

from agent import gtm_agent, pdf_exporter


class CleanKpiTests(unittest.TestCase):
    def test_keeps_valid_rows_and_caps_the_count(self):
        rows = [{"name": f"K{i}", "target": f"{i}%", "timeframe": "90 days"} for i in range(8)]
        self.assertEqual(len(gtm_agent._clean_kpis(rows)), 5)

    def test_skips_rows_missing_a_name_or_target(self):
        out = gtm_agent._clean_kpis([{"name": "", "target": "5"}, {"name": "x"}, "bad", {"name": "NPS", "target": 45}])
        self.assertEqual(out, [{"name": "NPS", "target": "45", "timeframe": ""}])

    def test_non_list_is_empty(self):
        self.assertEqual(gtm_agent._clean_kpis(None), [])


class PdfTargetsTests(unittest.TestCase):
    def _render(self, gtm):
        d = {"idea": "x", "targetCustomer": "y", "gtm": gtm}
        return pdf_exporter.generate_dossier_pdf(d)

    def test_pdf_still_builds_with_and_without_targets(self):
        base = {"positioning": "p", "channels": [{"text": "c", "tactics": [], "sourceIds": []}], "earlyCustomerApproach": "e"}
        self.assertTrue(self._render(base).startswith(b"%PDF"))
        full = dict(base, kpis=[{"name": "NPS", "target": "45", "timeframe": "6 months"}])
        self.assertTrue(self._render(full).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
