"""Tests for agent/llm.py's kickoff_with_fallback/_kickoff_cloud_chain -
specifically the fix for a real bug found via live testing: a model that
responds without raising (no rate limit, no missing-model error) but with
unparseable/wrong-shaped content used to short-circuit the entire fallback
chain instead of trying the remaining models, because the `validate`
callback was only ever checked against the chain's final return value, not
per-model inside the retry loop itself.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.llm import NeedsDeepAnalysisError, kickoff_with_fallback


class _FakeOutput:
    def __init__(self, raw):
        self.raw = raw
        self.token_usage = None


def _build_crew_returning(sequence):
    """sequence: dict[model] -> _FakeOutput | Exception instance."""
    calls = []

    def build_crew(model):
        calls.append(model)

        class _Crew:
            def kickoff(self):
                result = sequence[model]
                if isinstance(result, Exception):
                    raise result
                return result

        return _Crew()

    return build_crew, calls


class KickoffFallbackShapeValidationTests(unittest.TestCase):
    def test_a_shape_invalid_response_from_one_model_tries_the_next_model(self):
        # Primary responds but with content the validator rejects; the
        # fallback model responds with something valid - the chain must
        # reach and return the fallback's output, not give up after the
        # primary.
        sequence = {
            "primary-model": _FakeOutput("not valid json"),
            "fallback-model": _FakeOutput('{"ok": true}'),
        }
        build_crew, calls = _build_crew_returning(sequence)

        def validate(output):
            return output.raw.startswith("{")

        with patch("agent.llm.FALLBACK_MODELS", ("fallback-model",)):
            result = kickoff_with_fallback(build_crew, primary="primary-model", validate=validate)

        self.assertEqual(result.raw, '{"ok": true}')
        self.assertEqual(calls, ["primary-model", "fallback-model"])

    def test_shape_invalid_responses_from_every_model_raise_needs_deep_analysis(self):
        sequence = {
            "primary-model": _FakeOutput("garbage"),
            "fallback-model": _FakeOutput("also garbage"),
        }
        build_crew, calls = _build_crew_returning(sequence)

        def validate(output):
            return output.raw.startswith("{")

        with patch("agent.llm.FALLBACK_MODELS", ("fallback-model",)):
            with self.assertRaises(NeedsDeepAnalysisError):
                kickoff_with_fallback(build_crew, primary="primary-model", validate=validate)

        self.assertEqual(calls, ["primary-model", "fallback-model"])

    def test_a_valid_first_response_never_tries_the_fallback_model_at_all(self):
        sequence = {
            "primary-model": _FakeOutput('{"ok": true}'),
            "fallback-model": _FakeOutput('{"ok": true}'),
        }
        build_crew, calls = _build_crew_returning(sequence)

        def validate(output):
            return output.raw.startswith("{")

        with patch("agent.llm.FALLBACK_MODELS", ("fallback-model",)):
            kickoff_with_fallback(build_crew, primary="primary-model", validate=validate)

        self.assertEqual(calls, ["primary-model"])

    def test_no_validate_callback_accepts_whatever_the_first_model_returns(self):
        sequence = {"primary-model": _FakeOutput("anything at all")}
        build_crew, calls = _build_crew_returning(sequence)

        with patch("agent.llm.FALLBACK_MODELS", ()):
            result = kickoff_with_fallback(build_crew, primary="primary-model")

        self.assertEqual(result.raw, "anything at all")
        self.assertEqual(calls, ["primary-model"])


if __name__ == "__main__":
    unittest.main()
