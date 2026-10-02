import os
import unittest
from unittest.mock import patch

os.environ.setdefault("WEB_CACHE", "0")

from agent import pdf_exporter, verification


class AuditTests(unittest.TestCase):
    def test_records_removed_claims_and_that_the_check_ran(self):
        v = verification.Verdicts([True, False])
        v.ran, v.checked = True, 2
        claims = [{"text": "a", "sourceIds": ["src-1"]}, {"text": "b", "sourceIds": ["src-2"]}]
        self.assertEqual(verification.audit(claims, v), {"ran": True, "checked": 2, "removed": [{"text": "b", "sourceIds": ["src-2"]}]})

    def test_a_plain_list_or_failed_check_is_not_reported_as_run(self):
        self.assertFalse(verification.audit([{"text": "a", "sourceIds": ["s"]}], [True])["ran"])

    def test_verify_claims_marks_ran_only_when_the_model_answered(self):
        claims = [{"text": "a", "sourceIds": ["src-1"]}]
        with patch("agent.verification.kickoff_with_fallback", side_effect=RuntimeError("down")):
            self.assertFalse(verification.verify_claims("idea", claims, {"src-1": "text"}).ran)
        self.assertFalse(verification.verify_claims("idea", [{"text": "x", "sourceIds": []}], {}).ran)

    def test_pdf_builds_with_an_audit(self):
        d = {"idea": "x", "targetCustomer": "y",
             "swot": {"verification": {"ran": True, "checked": 5, "removed": [{"text": "bad claim", "sourceIds": ["src-1"]}]}}}
        self.assertTrue(pdf_exporter.generate_dossier_pdf(d).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
