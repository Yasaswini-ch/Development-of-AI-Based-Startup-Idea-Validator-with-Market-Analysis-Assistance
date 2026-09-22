"""
Prompt Loader Utility
----------------------
Loads externalized prompt templates from backend/agent/prompts/*.md at
runtime, with variable substitution via str.format(**kwargs). Keeps prompt
wording out of the agent modules so a prompt-only tweak shows up as an
isolated diff to one .md file instead of being buried inside agent logic.
"""

import os
from functools import lru_cache

_PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


@lru_cache(maxsize=32)
def _read_prompt_file(name: str) -> str:
    filepath = os.path.join(_PROMPTS_DIR, f"{name}.md")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_prompt(name: str, **kwargs) -> str:
    """Load prompts/{name}.md, substituting {placeholders} via str.format()
    when kwargs are given. Use {{double braces}} in the .md file for any
    literal brace that must survive formatting (e.g. a JSON example).
    """
    template = _read_prompt_file(name)
    if kwargs:
        return template.format(**kwargs)
    return template
