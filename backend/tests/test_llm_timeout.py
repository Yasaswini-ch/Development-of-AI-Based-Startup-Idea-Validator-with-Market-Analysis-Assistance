"""Milestone 4 / Track F - get_llm() always applies a call timeout.

Closes the "slow API responses" gap from the end-to-end error-path pass:
no LLM call anywhere had a timeout at all before this - a genuinely slow
(not rate-limited, not erroring) provider response had nothing bounding
it. This doesn't test actual provider latency (no real network call is
made here), only that every LLM object this app builds carries a timeout.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import unittest

from agent.llm import _LLM_CALL_TIMEOUT_SECONDS, get_llm


class GetLlmTimeoutTests(unittest.TestCase):
    def test_default_call_has_a_timeout(self):
        llm = get_llm()
        self.assertEqual(llm.timeout, _LLM_CALL_TIMEOUT_SECONDS)

    def test_call_with_max_tokens_still_has_a_timeout(self):
        # Every real call site (market/swot/mvp/gtm/chat_graph agents)
        # passes max_tokens - confirms the timeout isn't dropped once other
        # kwargs are present.
        llm = get_llm(max_tokens=450, model="groq/qwen/qwen3.8-27b")
        self.assertEqual(llm.timeout, _LLM_CALL_TIMEOUT_SECONDS)
        self.assertEqual(llm.max_tokens, 450)

    def test_unrecognized_model_still_gets_a_timeout(self):
        # A model outside _REASONING_EFFORT (e.g. a manual LLM_MODEL
        # override) must not lose the timeout just because it doesn't get
        # a reasoning_effort value.
        llm = get_llm(model="some/untested-model")
        self.assertEqual(llm.timeout, _LLM_CALL_TIMEOUT_SECONDS)

    def test_env_var_overrides_the_default(self):
        # _LLM_CALL_TIMEOUT_SECONDS is read at import time, so re-import
        # llm.py under the patched environment rather than relying on the
        # module-level constant already having been evaluated. The restore
        # reload must happen only after the env patch itself has been
        # undone (a `finally` inside the `with` block would still see the
        # patched value) so other tests in this file see the real default
        # again, not a leftover 12.
        import importlib

        import agent.llm as llm_module

        with patch.dict(os.environ, {"LLM_CALL_TIMEOUT_SECONDS": "12"}):
            importlib.reload(llm_module)
            llm = llm_module.get_llm()
            self.assertEqual(llm.timeout, 12.0)
        importlib.reload(llm_module)


if __name__ == "__main__":
    unittest.main()
