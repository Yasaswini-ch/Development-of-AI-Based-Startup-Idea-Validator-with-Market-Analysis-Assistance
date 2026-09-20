"""Tests for competitor_agent.py's Gemini price/feature-breadth
refinement pass (_refine_with_gemini) and how analyze_competitors merges
its output with the regex heuristics.

Standalone like test_milestone4_track_a.py: no fastapi/langgraph import
needed, just competitor_agent.py (which does need spaCy/en_core_web_sm -
already a hard dependency of the rest of this test suite via main.py).
"""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import competitor_agent


def _fake_response(body: dict):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(body).encode()

    return _Resp()


def _gemini_body(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class ValidGeminiPricingShapeTests(unittest.TestCase):
    def test_accepts_well_formed_entries(self):
        data = {"Acme": {"price": "mid", "featureBreadth": "broad"}}
        self.assertTrue(competitor_agent._valid_gemini_pricing_shape(data))

    def test_rejects_invalid_price_bucket(self):
        data = {"Acme": {"price": "cheap", "featureBreadth": "broad"}}
        self.assertFalse(competitor_agent._valid_gemini_pricing_shape(data))

    def test_rejects_invalid_breadth_bucket(self):
        data = {"Acme": {"price": "mid", "featureBreadth": "huge"}}
        self.assertFalse(competitor_agent._valid_gemini_pricing_shape(data))

    def test_rejects_non_dict_value(self):
        self.assertFalse(competitor_agent._valid_gemini_pricing_shape({"Acme": "mid"}))


class RefineWithGeminiTests(unittest.TestCase):
    def test_returns_empty_without_api_key(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("GEMINI_API_KEY", None)
            result = competitor_agent._refine_with_gemini(
                "Idea", [{"name": "Acme", "text": "Acme costs $15/mo."}]
            )
        self.assertEqual(result, {})

    def test_returns_empty_for_no_entries(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            result = competitor_agent._refine_with_gemini("Idea", [])
        self.assertEqual(result, {})

    def test_parses_valid_gemini_response(self):
        body = _gemini_body(json.dumps({"Acme": {"price": "mid", "featureBreadth": "broad"}}))
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch(
            "agent.competitor_agent.urllib.request.urlopen", return_value=_fake_response(body)
        ):
            result = competitor_agent._refine_with_gemini(
                "Idea", [{"name": "Acme", "text": "Acme costs $15/mo and offers broad tooling."}]
            )
        self.assertEqual(result["Acme"], {"price": "mid", "featureBreadth": "broad"})

    def test_rejects_response_naming_a_competitor_not_asked_about(self):
        # Gemini answering about a company it wasn't given (hallucinated
        # or copied from general knowledge) must never reach the caller.
        body = _gemini_body(json.dumps({"SomeoneElse": {"price": "mid", "featureBreadth": "broad"}}))
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch(
            "agent.competitor_agent.urllib.request.urlopen", return_value=_fake_response(body)
        ):
            result = competitor_agent._refine_with_gemini(
                "Idea", [{"name": "Acme", "text": "Acme costs $15/mo."}]
            )
        self.assertEqual(result, {})

    def test_network_failure_returns_empty_not_raises(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch(
            "agent.competitor_agent.urllib.request.urlopen", side_effect=TimeoutError("timed out")
        ):
            result = competitor_agent._refine_with_gemini(
                "Idea", [{"name": "Acme", "text": "Acme costs $15/mo."}]
            )
        self.assertEqual(result, {})

    def test_malformed_response_body_returns_empty_not_raises(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch(
            "agent.competitor_agent.urllib.request.urlopen",
            return_value=_fake_response({"unexpected": "shape"}),
        ):
            result = competitor_agent._refine_with_gemini(
                "Idea", [{"name": "Acme", "text": "Acme costs $15/mo."}]
            )
        self.assertEqual(result, {})


class AnalyzeCompetitorsRefinementMergeTests(unittest.TestCase):
    """analyze_competitors' merge rule: a regex-confident value is never
    overridden by Gemini; only genuine "unknown" gaps get filled.

    _extract_entities is mocked directly rather than relying on spaCy to
    tag a short synthetic sentence as ORG - confirmed live that
    en_core_web_sm often doesn't (e.g. "HelloFresh offers weekly meal
    kits..." tags no ORG at all), which is a real spaCy-on-contrived-text
    limitation, not something this merge logic should depend on to test
    reliably.
    """

    def _mock_mentions(self, price, breadth, local_text="Acme is a tool."):
        return {
            "Acme": {
                "count": 2,
                "source": {"url": "https://example.com/acme", "snippet": "Acme is a tool."},
                "has_context": True,
                "price": price,
                "breadth": breadth,
                "local_text": local_text,
            }
        }

    @patch("agent.competitor_agent._refine_with_gemini")
    @patch("agent.competitor_agent._dedupe_near_matches", return_value=["Acme"])
    @patch("agent.competitor_agent._extract_entities")
    @patch("agent.competitor_agent._nlp", new=object())
    def test_gemini_fills_unknown_price_and_breadth(self, mock_extract, _mock_dedupe, mock_refine):
        mock_extract.return_value = self._mock_mentions(price=None, breadth=None)
        mock_refine.return_value = {"Acme": {"price": "high", "featureBreadth": "narrow"}}
        result = competitor_agent.analyze_competitors("Idea", "Target", "Problem", [])
        acme = result["competitors"][0]
        self.assertEqual(acme["estimatedPrice"], "high")
        self.assertEqual(acme["featureBreadth"], "narrow")
        mock_refine.assert_called_once()

    @patch("agent.competitor_agent._refine_with_gemini")
    @patch("agent.competitor_agent._dedupe_near_matches", return_value=["Acme"])
    @patch("agent.competitor_agent._extract_entities")
    @patch("agent.competitor_agent._nlp", new=object())
    def test_regex_confident_value_is_never_overridden(self, mock_extract, _mock_dedupe, mock_refine):
        # Regex already found a confident "high" - Gemini disagreeing with
        # "low" must never reach the response.
        mock_extract.return_value = self._mock_mentions(price="high", breadth=None)
        mock_refine.return_value = {"Acme": {"price": "low", "featureBreadth": "narrow"}}
        result = competitor_agent.analyze_competitors("Idea", "Target", "Problem", [])
        acme = result["competitors"][0]
        self.assertEqual(acme["estimatedPrice"], "high")
        self.assertEqual(acme["featureBreadth"], "narrow")  # breadth was the genuine gap

    @patch("agent.competitor_agent._refine_with_gemini")
    @patch("agent.competitor_agent._dedupe_near_matches", return_value=["Acme"])
    @patch("agent.competitor_agent._extract_entities")
    @patch("agent.competitor_agent._nlp", new=object())
    def test_no_gemini_call_when_regex_already_found_everything(self, mock_extract, _mock_dedupe, mock_refine):
        mock_extract.return_value = self._mock_mentions(price="high", breadth="broad")
        competitor_agent.analyze_competitors("Idea", "Target", "Problem", [])
        mock_refine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
