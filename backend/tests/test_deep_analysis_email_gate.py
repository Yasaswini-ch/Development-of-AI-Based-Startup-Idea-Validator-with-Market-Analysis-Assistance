"""Regression tests for the "enter your email for deeper analysis" detour.

The bug: on a hosted deployment with no local Ollama tier, an anonymous
founder whose first /validate hit a momentary cloud-quota squeeze was told
the idea "needs deeper analysis" and asked for an email. Entering one never
unlocked a deeper model - it only switched on the second cloud pass and the
deterministic fallback, which then showed results in the browser anyway.
Now /validate only asks for an email when a local tier really exists, and
kickoff_with_fallback retries the cloud chain for everyone.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import llm
from agent.graph import NEEDS_DEEP_ANALYSIS
from agent.llm import NeedsDeepAnalysisError, kickoff_with_fallback

_PAYLOAD = {"idea": "A meal kit for busy families", "targetCustomer": "Working parents", "problem": "No time to cook"}


def _ok_state():
    return {
        "summary": "A promising idea.",
        "results": [],
        "marketOpportunity": {"marketSize": "text", "trends": [], "segments": [], "degraded": True},
        "errors": {},
    }


class ValidateEmailGateTests(unittest.TestCase):
    def setUp(self):
        main._clear_cache()
        main._clear_rate_limits()
        self.client = TestClient(main.app)

    def test_without_a_local_tier_an_anonymous_request_never_asks_for_email(self):
        with patch("main.local_llm_available", return_value=False), patch(
            "main.pipeline.invoke", return_value=_ok_state()
        ) as invoke:
            res = self.client.post("/validate", json=_PAYLOAD)

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertNotIn("needsEmailForDeepAnalysis", body)
        self.assertEqual(body["summary"], "A promising idea.")
        # The first (and only) run already takes the retry + fallback path
        # an email used to unlock.
        self.assertTrue(invoke.call_args.args[0]["allowLocalLlm"])

    def test_with_a_local_tier_an_exhausted_anonymous_request_still_asks_for_email(self):
        with patch("main.local_llm_available", return_value=True), patch(
            "main.pipeline.invoke", return_value={"error": NEEDS_DEEP_ANALYSIS}
        ) as invoke:
            res = self.client.post("/validate", json=_PAYLOAD)

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["needsEmailForDeepAnalysis"])
        self.assertFalse(invoke.call_args.args[0]["allowLocalLlm"])


class _FakeOutput:
    def __init__(self, raw):
        self.raw = raw
        self.token_usage = None


class _Crew:
    def __init__(self, result):
        self._result = result

    def kickoff(self):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class CloudRetryTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("agent.llm._CLOUD_RETRY_COOLDOWN_SECONDS", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_transient_exhaustion_is_retried_once_without_needing_an_email(self):
        calls = []

        def build_crew(model):
            calls.append(model)
            # First pass: rate limited everywhere. Second pass: recovered.
            if len(calls) <= 2:
                return _Crew(RuntimeError("rate_limit_exceeded"))
            return _Crew(_FakeOutput("GOOD"))

        with patch("agent.llm.FALLBACK_MODELS", ("fallback-model",)):
            result = kickoff_with_fallback(build_crew, primary="primary-model")

        self.assertEqual(result.raw, "GOOD")
        self.assertEqual(calls, ["primary-model", "fallback-model", "primary-model"])

    def test_still_raises_needs_deep_analysis_when_the_retry_also_fails(self):
        def build_crew(model):
            return _Crew(RuntimeError("rate_limit_exceeded"))

        with patch("agent.llm.FALLBACK_MODELS", ("fallback-model",)):
            with self.assertRaises(NeedsDeepAnalysisError):
                kickoff_with_fallback(build_crew, primary="primary-model")

    def test_an_unreachable_local_tier_is_skipped_on_the_allow_local_path(self):
        calls = []

        def build_crew(model):
            calls.append(model)
            return _Crew(RuntimeError("rate_limit_exceeded"))

        with patch("agent.llm.FALLBACK_MODELS", ()), patch("agent.llm.local_llm_available", return_value=False):
            with self.assertRaises(RuntimeError):
                kickoff_with_fallback(build_crew, primary="primary-model", allow_local=True)

        self.assertNotIn(llm.LOCAL_MODEL, calls)


class LocalProbeTests(unittest.TestCase):
    def setUp(self):
        llm._local_probe_cache.update(checkedAt=0.0, available=False)
        self.addCleanup(llm._local_probe_cache.update, checkedAt=0.0, available=False)

    def test_unreachable_ollama_reports_unavailable(self):
        with patch("agent.llm._OLLAMA_BASE_URL", "http://127.0.0.1:9"):
            self.assertFalse(llm.local_llm_available())


if __name__ == "__main__":
    unittest.main()
