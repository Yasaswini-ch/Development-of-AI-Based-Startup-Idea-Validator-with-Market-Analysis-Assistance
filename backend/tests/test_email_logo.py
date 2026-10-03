import os
import unittest
from unittest.mock import patch

from agent import email_delivery


class EmailLogoTests(unittest.TestCase):
    def test_logo_only_for_a_public_https_site(self):
        with patch.dict(os.environ, {"FRONTEND_ORIGIN": "https://affinity.example.com/"}):
            html = email_delivery._logo_html()
        self.assertIn('src="https://affinity.example.com/logo.png"', html)
        for origin in ("http://localhost:5173", ""):
            with patch.dict(os.environ, {"FRONTEND_ORIGIN": origin}):
                self.assertEqual(email_delivery._logo_html(), "")


if __name__ == "__main__":
    unittest.main()
