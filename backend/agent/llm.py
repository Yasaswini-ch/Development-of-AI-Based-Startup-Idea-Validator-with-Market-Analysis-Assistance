import logging
import os
import re
import time

from crewai import LLM

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "groq/qwen/qwen3.6-27b"
_MAX_RETRY_WAIT_SECONDS = 30


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


def _retry_after_seconds(exc: Exception) -> float | None:
    """Groq's rate-limit error message names its own cooldown, e.g. "Please
    try again in 25.545s" - parse that instead of guessing a backoff.
    Returns None for anything that isn't this specific, recoverable error.
    """
    match = re.search(r"try again in ([\d.]+)s", str(exc))
    return float(match.group(1)) if match else None


def kickoff_with_retry(crew, max_attempts: int = 2):
    """Run a CrewAI crew, retrying once on a Groq rate-limit error using the
    wait time Groq itself reports (capped so a request can't hang forever).

    A same-request fallback to a second LLM provider (Gemini, using the key
    already in .env) was tried and reverted: it doesn't fail fast on a bad
    call, it hangs for minutes past its own timeout parameter before ever
    raising - confirmed by direct testing, not just the litellm/CrewAI
    message-format issues noted in get_llm's docstring. That's worse than
    the honest static fallback content the caller already returns, so it's
    not a usable fallback with our pinned litellm version. Retrying the same
    model after its own suggested cooldown is the fix that's actually been
    verified to work end-to-end.
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return crew.kickoff()
        except Exception as exc:
            last_exc = exc
            wait = _retry_after_seconds(exc)
            if wait is None or attempt == max_attempts - 1:
                raise
            wait = min(wait, _MAX_RETRY_WAIT_SECONDS) + 0.5
            logger.warning("Rate limited, retrying in %.1fs: %s", wait, exc)
            time.sleep(wait)
    raise last_exc
