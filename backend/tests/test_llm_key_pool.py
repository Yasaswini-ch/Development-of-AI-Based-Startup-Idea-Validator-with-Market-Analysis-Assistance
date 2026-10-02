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
        llm._key_cooldowns.clear()

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


class CooldownTests(KeyEnvCase):
    def setUp(self):
        super().setUp()
        os.environ["GROQ_API_KEYS"] = "a,b"

    def test_the_retry_hint_in_the_error_text_is_parsed(self):
        exc = Exception("Rate limit reached ... on tokens per day (TPD). Please try again in 2m9.168s. Need more tokens?")
        self.assertAlmostEqual(llm._key_cooldown_seconds(exc), 129.168, places=2)
        self.assertEqual(llm._key_cooldown_seconds(Exception("try again in 6.2s")), 6.2)
        self.assertEqual(llm._key_cooldown_seconds(Exception("try again in 1h2m3s")), 3723.0 if 3723.0 <= llm._MAX_KEY_COOLDOWN_SECONDS else llm._MAX_KEY_COOLDOWN_SECONDS)

    def test_no_hint_gets_a_short_default_and_a_huge_value_is_capped(self):
        self.assertEqual(llm._key_cooldown_seconds(Exception("rate_limit_exceeded")), llm._DEFAULT_KEY_COOLDOWN_SECONDS)
        self.assertEqual(llm._key_cooldown_seconds(Exception("try again in 9h0m0s")), llm._MAX_KEY_COOLDOWN_SECONDS)

    def test_a_limited_key_goes_last_for_that_model_only(self):
        llm._mark_key_limited(GROQ_MODEL, "a", Exception("try again in 60s"))
        self.assertEqual(llm._key_order("groq", GROQ_MODEL)[0], "b")
        self.assertEqual(llm._key_order("groq", GROQ_MODEL)[0], "b")  # stays last however the rotation turns
        other = {llm._key_order("groq", "groq/openai/gpt-oss-120b")[0], llm._key_order("groq", "groq/openai/gpt-oss-120b")[0]}
        self.assertEqual(other, {"a", "b"})  # a different model is unaffected

    def test_when_every_key_is_limited_all_are_still_tried_soonest_first(self):
        llm._mark_key_limited(GROQ_MODEL, "a", Exception("try again in 120s"))
        llm._mark_key_limited(GROQ_MODEL, "b", Exception("try again in 10s"))
        self.assertEqual(llm._key_order("groq", GROQ_MODEL), ["b", "a"])

    def test_a_key_is_usable_again_after_its_cooldown(self):
        llm._mark_key_limited(GROQ_MODEL, "a", Exception("try again in 5s"))
        later = llm.time.time() + 6
        with patch("agent.llm.time.time", return_value=later):
            self.assertEqual(set(llm._key_order("groq", GROQ_MODEL)), {"a", "b"})
            self.assertNotEqual(llm._key_order("groq", GROQ_MODEL)[-1:], [])  # both present, none parked

    def test_a_rate_limit_in_the_chain_parks_that_key_for_later_calls(self):
        calls = []

        def kickoff(model, build_crew):
            key = llm._active_key.get()[1]
            calls.append(key)
            if key == "a":
                raise Exception("RateLimitError rate_limit_exceeded try again in 120s")
            return "OK"

        with patch("agent.llm._kickoff_with_metrics", side_effect=kickoff):
            for _ in range(3):
                llm._kickoff_cloud_chain(lambda m: None, GROQ_MODEL)
        # "a" fails at most once; after that it is skipped, so later calls go straight to "b"
        self.assertEqual(calls.count("a"), 1)
        self.assertEqual(calls.count("b"), 3)


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



class TokenBudgetTests(unittest.TestCase):
    def test_qwen_stays_under_its_hard_output_cap(self):
        self.assertEqual(llm._token_budget("groq/qwen/qwen3.8-27b", 900), 900)
        self.assertEqual(llm._token_budget("groq/qwen/qwen3.8-27b", 2000), 950)

    def test_gpt_oss_models_get_room_for_their_reasoning(self):
        # measured: SWOT needed about 1,100-1,600 on 20b and 2,241 on 120b against a 900 limit
        self.assertGreaterEqual(llm._token_budget("groq/openai/gpt-oss-20b", 900), 1600)
        self.assertGreaterEqual(llm._token_budget("groq/openai/gpt-oss-20b", 600), 1100)  # MVP needed about 1,100
        self.assertGreaterEqual(llm._token_budget("groq/openai/gpt-oss-120b", 900), 2241)

    def test_small_requests_still_get_a_workable_floor(self):
        self.assertEqual(llm._token_budget("groq/openai/gpt-oss-20b", 400), 1500)
        self.assertEqual(llm._token_budget("groq/openai/gpt-oss-120b", 400), 1500)

    def test_gemini_gets_a_moderate_increase_and_unknown_models_are_untouched(self):
        self.assertEqual(llm._token_budget("gemini/gemini-3.6-flash", 600), 900)
        self.assertEqual(llm._token_budget("ollama/qwen2.5:7b", 600), 600)

    def test_no_limit_means_no_limit(self):
        self.assertIsNone(llm._token_budget("groq/openai/gpt-oss-20b", None))

    @patch("agent.llm.LLM")
    def test_get_llm_applies_the_per_model_budget(self, llm_cls):
        llm.get_llm(max_tokens=900, model="groq/openai/gpt-oss-120b")
        self.assertEqual(llm_cls.call_args.kwargs["max_tokens"], 2700)
        llm.get_llm(max_tokens=900, model="groq/qwen/qwen3.8-27b")
        self.assertEqual(llm_cls.call_args.kwargs["max_tokens"], 900)


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
