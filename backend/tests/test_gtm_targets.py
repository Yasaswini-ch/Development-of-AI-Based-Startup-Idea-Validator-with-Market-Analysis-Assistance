import os
import unittest

os.environ.setdefault("WEB_CACHE", "0")

from agent import gtm_agent, pdf_exporter


class CleanAcquisitionTests(unittest.TestCase):
    def test_keeps_a_numeric_range_and_labels_currency(self):
        out = gtm_agent._clean_acquisition({"primaryMethod": " Partner referrals ", "estimatedCac": {"low": "30", "high": 55, "basis": "typical"}})
        self.assertEqual(out["primaryMethod"], "Partner referrals")
        self.assertEqual(out["estimatedCac"], {"low": 30.0, "high": 55.0, "currency": "USD", "basis": "typical"})

    def test_drops_an_inverted_or_non_numeric_range(self):
        self.assertIsNone(gtm_agent._clean_acquisition({"estimatedCac": {"low": 90, "high": 10}}))
        self.assertIsNone(gtm_agent._clean_acquisition({"estimatedCac": {"low": "cheap", "high": "dear"}}))
        self.assertIsNone(gtm_agent._clean_acquisition("nope"))

    def test_method_survives_without_a_range(self):
        self.assertEqual(gtm_agent._clean_acquisition({"primaryMethod": "SEO"}), {"primaryMethod": "SEO"})


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
        full = dict(base, acquisition={"primaryMethod": "Referrals", "estimatedCac": {"low": 30, "high": 55, "currency": "USD", "basis": "b"}},
                    kpis=[{"name": "NPS", "target": "45", "timeframe": "6 months"}])
        self.assertTrue(self._render(full).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
