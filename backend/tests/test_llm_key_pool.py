"""API key pool (several keys per provider) and per-agent execution ceilings."""

import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEB_CACHE", "0")
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import llm

RATE_LIMIT = Exception("litellm.RateLimitError: GroqException - rate_limit_exceeded")
GROQ_MODEL = "groq/openai/gpt-oss-20b"


class KeyEnvCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for name in ("GROQ_API_KEYS", "GROQ_API_KEY", "GEMINI_API_KEYS", "GEMINI_API_KEY", "LLM_FALLBACK_MODELS", "LLM_MODEL"):
            os.environ.pop(name, None)
        llm._key_counters.clear()

    def tearDown(self):
        self.env.stop()


class KeyListTests(KeyEnvCase):
    def test_no_keys_means_no_pool(self):
        self.assertEqual(llm._keys_for("groq"), [])

    def test_the_single_key_still_works_on_its_own(self):
        os.environ["GROQ_API_KEY"] = "solo"
        self.assertEqual(llm._keys_for("groq"), ["solo"])

    def test_a_comma_separated_list_is_split_and_trimmed(self):
        os.environ["GROQ_API_KEYS"] = " a , b ,, c "
        self.assertEqual(llm._keys_for("groq"), ["a", "b", "c"])

    def test_the_single_key_is_added_once_if_not_already_listed(self):
        os.environ["GROQ_API_KEYS"] = "a,b"
        os.environ["GROQ_API_KEY"] = "c"
        self.assertEqual(llm._keys_for("groq"), ["a", "b", "c"])
        os.environ["GROQ_API_KEY"] = "a"
        self.assertEqual(llm._keys_for("groq"), ["a", "b"])

    def test_providers_are_separate(self):
        os.environ["GROQ_API_KEYS"] = "g1,g2"
        os.environ["GEMINI_API_KEY"] = "m1"
        self.assertEqual(llm._keys_for("gemini"), ["m1"])

    def test_consecutive_calls_start_on_different_keys(self):
        os.environ["GROQ_API_KEYS"] = "a,b"
        self.assertEqual(llm._key_order("groq"), ["a", "b"])
        self.assertEqual(llm._key_order("groq"), ["b", "a"])
        self.assertEqual(llm._key_order("groq"), ["a", "b"])


class GetLlmKeyTests(KeyEnvCase):
    @patch("agent.llm.LLM")
    def test_the_pools_chosen_key_is_passed_to_the_client(self, llm_cls):
        token = llm._active_key.set(("groq", "chosen-key"))
        try:
            llm.get_llm(model=GROQ_MODEL)
        finally:
            llm._active_key.reset(token)
        self.assertEqual(llm_cls.call_args.kwargs["api_key"], "chosen-key")

    @patch("agent.llm.LLM")
    def test_a_key_for_another_provider_is_not_used(self, llm_cls):
        token = llm._active_key.set(("gemini", "gemini-key"))
        try:
            llm.get_llm(model=GROQ_MODEL)
        finally:
            llm._active_key.reset(token)
        self.assertNotIn("api_key", llm_cls.call_args.kwargs)

    @patch("agent.llm.LLM")
    def test_without_a_pool_the_client_is_built_as_before(self, llm_cls):
        llm.get_llm(model=GROQ_MODEL)
        self.assertNotIn("api_key", llm_cls.call_args.kwargs)


class ChainTests(KeyEnvCase):
    def _run(self, fake, primary=GROQ_MODEL):
        attempts = []

        def kickoff(model, build_crew):
            active = llm._active_key.get()
            attempts.append((model, active[1] if active else None))
            return fake(model, active)

        with patch("agent.llm._kickoff_with_metrics", side_effect=kickoff):
            result = llm._kickoff_cloud_chain(lambda m: None, primary)
        return result, attempts

    def test_a_rate_limit_retries_the_same_model_on_the_next_key(self):
        os.environ["GROQ_API_KEYS"] = "k1,k2"

        def fake(model, active):
            if active[1] == "k1":
                raise RATE_LIMIT
            return "OK"

        result, attempts = self._run(fake)
        self.assertEqual(result, "OK")
        self.assertEqual(attempts, [(GROQ_MODEL, "k1"), (GROQ_MODEL, "k2")])  # same model, no downgrade

    def test_when_every_key_is_limited_the_chain_moves_to_the_next_model(self):
        os.environ["GROQ_API_KEYS"] = "k1,k2"

        def fake(model, active):
            if model.startswith("groq/"):
                raise RATE_LIMIT
            return "from-gemini"

        result, attempts = self._run(fake)
        self.assertEqual(result, "from-gemini")
        groq_attempts = [a for a in attempts if a[0].startswith("groq/")]
        # each Groq model was tried on both keys before moving on
        self.assertEqual(sorted({k for _, k in groq_attempts}), ["k1", "k2"])
        self.assertTrue(attempts[-1][0].startswith("gemini/"))

    def test_a_single_key_behaves_exactly_as_before(self):
        os.environ["GROQ_API_KEY"] = "only"

        def fake(model, active):
            if model == GROQ_MODEL:
                raise RATE_LIMIT
            return "next-model"

        result, attempts = self._run(fake)
        self.assertEqual(result, "next-model")
        self.assertEqual(attempts[0], (GROQ_MODEL, None))  # no pool, no explicit key
        self.assertEqual(len([a for a in attempts if a[0] == GROQ_MODEL]), 1)

    def test_a_bad_answer_does_not_waste_the_other_key(self):
        os.environ["GROQ_API_KEYS"] = "k1,k2"

        def fake(model, active):
            if model == GROQ_MODEL:
                raise llm._ShapeValidationError("not JSON")
            return "next-model"

        result, attempts = self._run(fake)
        self.assertEqual(result, "next-model")
        self.assertEqual(len([a for a in attempts if a[0] == GROQ_MODEL]), 1)  # a bad answer is not a key problem

    def test_calls_alternate_which_key_goes_first(self):
        os.environ["GROQ_API_KEYS"] = "k1,k2"
        _, first = self._run(lambda m, a: "OK")
        _, second = self._run(lambda m, a: "OK")
        self.assertEqual([first[0][1], second[0][1]], ["k1", "k2"])

    def test_the_active_key_is_cleared_after_each_attempt(self):
        os.environ["GROQ_API_KEYS"] = "k1,k2"
        self._run(lambda m, a: "OK")
        self.assertIsNone(llm._active_key.get())

    def test_keys_never_appear_in_the_logs(self):
        os.environ["GROQ_API_KEYS"] = "gsk_SECRET_ONE,gsk_SECRET_TWO"

        def fake(model, active):
            if active[1] == "gsk_SECRET_ONE":
                raise RATE_LIMIT
            return "OK"

        with self.assertLogs("agent.llm", level="WARNING") as logs:
            self._run(fake)
        text = "\n".join(logs.output)
        self.assertIn("key 1 of 2", text)
        self.assertNotIn("gsk_SECRET", text)


class AgentCeilingTests(unittest.TestCase):
    FILES = [
        "market_agent.py", "competitor_agent.py", "swot_agent.py", "mvp_agent.py", "gtm_agent.py",
        "assumption_agent.py", "revenue_agent.py", "verification.py", "chat_graph.py",
    ]

    def test_every_agent_sets_an_execution_ceiling_and_an_iteration_cap(self):
        for filename in self.FILES:
            source = (BACKEND_DIR / "agent" / filename).read_text(encoding="utf-8")
            self.assertIn("max_execution_time=AGENT_MAX_EXECUTION_SECONDS", source, filename)
            self.assertIn("max_iter=AGENT_MAX_ITER", source, filename)

    def test_the_ceilings_are_tighter_than_crewais_defaults(self):
        self.assertLessEqual(llm.AGENT_MAX_ITER, 5)  # CrewAI's default is 20, each re-prompt a paid call
        self.assertGreater(llm.AGENT_MAX_EXECUTION_SECONDS, llm._LLM_CALL_TIMEOUT_SECONDS)  # more than one call's timeout


if __name__ == "__main__":
    unittest.main()
