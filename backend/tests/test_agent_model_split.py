"""Which model each agent starts on: spread across rate-limit buckets, never
six agents on one model again."""

import os
import re
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import llm

QWEN = "groq/qwen/qwen3.8-27b"
AGENT_FILES = {
    "market": "market_agent.py",
    "competitor": "competitor_agent.py",
    "swot": "swot_agent.py",
    "mvp": "mvp_agent.py",
    "gtm": "gtm_agent.py",
    "assumptions": "assumption_agent.py",
    "revenue": "revenue_agent.py",
    "verification": "verification.py",
    "advisor": "chat_graph.py",
}


class ModelMapTests(unittest.TestCase):
    def test_every_llm_agent_has_a_primary(self):
        self.assertEqual(set(llm.AGENT_PRIMARY_MODELS), set(AGENT_FILES))

    def test_only_market_starts_on_the_1000_token_per_minute_model(self):
        # That model's cap leaves room for one call a minute, and its 950-token
        # output ceiling is too small for most agents' answers (the assumption
        # tracker needs about 1,500 and failed the shape check on it every time).
        on_qwen = [a for a, m in llm.AGENT_PRIMARY_MODELS.items() if m == QWEN]
        self.assertEqual(on_qwen, ["market"])

    def test_mvp_and_gtm_run_in_parallel_so_they_use_different_models(self):
        self.assertNotEqual(llm.primary_for("mvp"), llm.primary_for("gtm"))

    def test_no_model_carries_more_than_four_agents(self):
        counts = Counter(llm.AGENT_PRIMARY_MODELS.values())
        self.assertLessEqual(max(counts.values()), 4)
        self.assertGreaterEqual(len(counts), 3)

    def test_swot_go_to_market_and_revenue_share_the_120b_models_pool_of_accounts(self):
        # They run within about 40 seconds of each other. On ONE Groq account that is more
        # than the model's 8,000 tokens a minute (revenue models fell back to the rule-based
        # result), so this only works because GROQ_API_KEYS pools several accounts.
        models = {llm.primary_for(a) for a in ("swot", "gtm", "revenue")}
        self.assertEqual(models, {"groq/openai/gpt-oss-120b"})

    def test_gemini_free_quota_goes_only_to_the_advisor(self):
        gemini = sorted(a for a, m in llm.AGENT_PRIMARY_MODELS.items() if m.startswith("gemini/"))
        self.assertEqual(gemini, ["advisor"])  # about 20 requests a day per model

    def test_every_primary_has_a_reasoning_effort_entry_unless_deliberately_without_one(self):
        # gemini-3.8-flash has no entry on purpose (see _REASONING_EFFORT's comments).
        for agent, model in llm.AGENT_PRIMARY_MODELS.items():
            if model == "gemini/gemini-3.8-flash":
                continue
            self.assertTrue(model in llm._REASONING_EFFORT, f"{agent}: {model} has no reasoning_effort entry")


class OverrideTests(unittest.TestCase):
    def test_an_environment_variable_re_points_one_agent(self):
        with patch.dict(os.environ, {"AGENT_MODEL_SWOT": "groq/openai/gpt-oss-20b"}):
            self.assertEqual(llm.primary_for("swot"), "groq/openai/gpt-oss-20b")
            self.assertEqual(llm.primary_for("mvp"), llm.AGENT_PRIMARY_MODELS["mvp"])  # others unaffected

    def test_an_unknown_agent_falls_back_to_the_default_model(self):
        self.assertEqual(llm.primary_for("not-an-agent"), llm.DEFAULT_MODEL)


class WiringTests(unittest.TestCase):
    """Each agent module must actually ask for its own primary, not rely on the default."""

    def test_each_agent_module_passes_its_primary_to_the_fallback_chain(self):
        for agent, filename in AGENT_FILES.items():
            source = (BACKEND_DIR / "agent" / filename).read_text(encoding="utf-8")
            self.assertRegex(source, rf'primary=primary_for\("{agent}"\)', f"{filename} does not use primary_for({agent!r})")

    def test_no_agent_hardcodes_a_model_name_any_more(self):
        for filename in AGENT_FILES.values():
            source = (BACKEND_DIR / "agent" / filename).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r'primary="(groq|gemini)/', source), f"{filename} hardcodes a primary model")


if __name__ == "__main__":
    unittest.main()
