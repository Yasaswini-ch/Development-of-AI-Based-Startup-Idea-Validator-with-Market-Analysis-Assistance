"""Regression coverage for a bug found during manual testing: the fallback
chain in agent/llm.py only advanced to the next model on a rate limit or
model_not_found error. A model that responded successfully at the network
level but with a malformed/unparseable shape (CrewOutput.raw not matching
the expected JSON contract) was treated as "done" and returned immediately
- the `validate` shape check only ran one level up, in kickoff_with_fallback,
after the chain had already committed to that one model's output.

Repro this caught live: primary rate-limited, switched to fallback 1, which
returned bad-shaped JSON (after CrewAI's own internal retries) but never
raised - the chain stopped right there and never even tried fallback 2 or
fallback 3, despite both being fully available. This file locks in the fix:
a validate() failure now gets the exact same immediate-switch treatment as
a rate limit, inside _kickoff_cloud_chain itself.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.llm import FALLBACK_MODELS, NeedsDeepAnalysisError, kickoff_with_fallback


class FakeOutput:
    def __init__(self, raw):
        self.raw = raw
        self.token_usage = None


class FakeCrew:
    def __init__(self, result):
        self._result = result

    def kickoff(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _rate_limit_error():
    return Exception("rate_limit_exceeded: try again in 0.01s")


def _valid_shape(output):
    return output.raw == "GOOD"


class ShapeValidationFallbackTests(unittest.TestCase):
    """The 4-model chain here mirrors the real one: primary + the 3
    FALLBACK_MODELS (currently gpt-oss-20b, gpt-oss-120b, gemini)."""

    def test_advances_past_a_network_successful_but_malformed_response(self):
        # Primary rate-limited, fallback 1 responds but with a bad shape,
        # fallback 2 is good - the chain must reach fallback 2, not stop at
        # fallback 1's broken response.
        calls = []

        def build_crew(model):
            calls.append(model)
            if len(calls) == 1:
                return FakeCrew(_rate_limit_error())
            if len(calls) == 2:
                return FakeCrew(FakeOutput("BAD SHAPE, NOT WHAT VALIDATE WANTS"))
            return FakeCrew(FakeOutput("GOOD"))

        result = kickoff_with_fallback(build_crew, validate=_valid_shape)

        self.assertEqual(result.raw, "GOOD")
        self.assertEqual(len(calls), 3)
        # Every model actually attempted must be distinct - a bug that kept
        # retrying the same model instead of advancing would show up here
        # as a duplicate.
        self.assertEqual(len(set(calls)), 3)

    def test_does_not_stop_at_the_first_malformed_response_even_without_a_prior_rate_limit(self):
        # No rate limit at all here - fallback purely on shape.
        calls = []

        def build_crew(model):
            calls.append(model)
            if len(calls) < 2:
                return FakeCrew(FakeOutput("BAD"))
            return FakeCrew(FakeOutput("GOOD"))

        result = kickoff_with_fallback(build_crew, validate=_valid_shape)
        self.assertEqual(result.raw, "GOOD")
        self.assertEqual(len(calls), 2)

    def test_tries_every_model_in_the_chain_before_giving_up(self):
        calls = []

        def build_crew(model):
            calls.append(model)
            return FakeCrew(FakeOutput("BAD"))

        with self.assertRaises(NeedsDeepAnalysisError):
            kickoff_with_fallback(build_crew, validate=_valid_shape)

        # Primary + all 3 configured fallbacks, not just the first one that
        # happened to respond with a bad shape.
        self.assertEqual(len(calls), 1 + len(FALLBACK_MODELS))
        self.assertEqual(len(set(calls)), 1 + len(FALLBACK_MODELS))

    def test_falls_back_to_local_model_when_allow_local_and_every_cloud_model_is_malformed(self):
        cloud_calls = []

        def build_crew(model):
            if model == "ollama/qwen2.5:7b":
                return FakeCrew(FakeOutput("GOOD"))
            cloud_calls.append(model)
            return FakeCrew(FakeOutput("BAD"))

        result = kickoff_with_fallback(build_crew, allow_local=True, validate=_valid_shape)

        self.assertEqual(result.raw, "GOOD")
        self.assertEqual(len(cloud_calls), 1 + len(FALLBACK_MODELS))

    def test_a_bug_inside_validate_itself_is_not_treated_as_switch_worthy(self):
        # allow_local=False always wraps whatever propagates out of the
        # cloud chain as NeedsDeepAnalysisError (pre-existing, documented
        # behavior, unrelated to this fix) - what this actually checks is
        # that a broken validate() aborts on the spot rather than being
        # swallowed the same way a rate limit or bad shape is: only one
        # model should ever get called, not the whole chain.
        calls = []

        def build_crew(model):
            calls.append(model)
            return FakeCrew(FakeOutput("anything"))

        def broken_validate(output):
            raise RuntimeError("boom - a real bug in the validator")

        with self.assertRaises(NeedsDeepAnalysisError) as ctx:
            kickoff_with_fallback(build_crew, validate=broken_validate)

        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)
        self.assertEqual(len(calls), 1)

    def test_a_non_rate_limit_non_shape_error_still_raises_immediately_without_trying_fallbacks(self):
        calls = []

        def build_crew(model):
            calls.append(model)
            return FakeCrew(RuntimeError("some unrelated real bug, not a rate limit or bad shape"))

        with self.assertRaises(NeedsDeepAnalysisError):
            kickoff_with_fallback(build_crew, validate=_valid_shape)

        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
