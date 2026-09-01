import os

from crewai import LLM

DEFAULT_MODEL = "groq/qwen/qwen3.6-27b"


def get_llm(max_tokens: int | None = None):
    """LLM used by every CrewAI agent, via LiteLLM.

    Set LLM_MODEL to override (e.g. "gemini/gemini-3.6-flash", "openai/gpt-4o-mini").
    Groq needs GROQ_API_KEY; Gemini needs GEMINI_API_KEY; OpenAI needs OPENAI_API_KEY.

    Tried switching to Gemini for a higher rate limit, but its current models
    either need newer message formatting our pinned LiteLLM version doesn't
    support (3.x models hit "Requests ending with a model turn are not
    supported") or are deprecated for new API keys (2.x models). Reverted to
    Groq, which is confirmed working end-to-end - pace test submissions ~60s
    apart to stay under its free-tier rate limit.

    Returns a plain model string by default (proven reliable for the Web
    Search Agent's summary). Only pass max_tokens for an agent that's
    specifically running out of room - we found that raising the default
    for every agent made this model MORE likely to ramble through a visible
    chain-of-thought instead of answering directly, not less, so don't
    apply it globally.
    """
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    if max_tokens is None:
        return model
    return LLM(model=model, max_tokens=max_tokens)
