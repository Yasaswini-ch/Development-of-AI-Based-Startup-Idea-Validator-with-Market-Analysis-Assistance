import logging
import os
import re
import time

from crewai import LLM

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "groq/qwen/qwen3.6-27b"

# A second, different model hosted on the *same* Groq account. Groq applies
# rate limits per model, not per account - confirmed via `GET
# /openai/v1/models` against our own key and a direct latency test (both
# respond in under a second, nothing like Gemini's multi-minute hang below).
# So this isn't a cross-provider fallback (the kind that was tried and
# reverted - see kickoff_with_fallback's docstring), it's a second bucket on
# infrastructure we already know works, which is exactly what actually
# distributes load instead of just adding failure risk.
FALLBACK_MODEL = "groq/openai/gpt-oss-20b"
_MAX_RETRY_WAIT_SECONDS = 30


def get_llm(max_tokens: int | None = None, model: str | None = None):
    """LLM used by every CrewAI agent, via LiteLLM.

    Set LLM_MODEL to override the primary model, LLM_FALLBACK_MODEL to
    override the fallback (see FALLBACK_MODEL above and
    kickoff_with_fallback). Groq needs GROQ_API_KEY.

    A same-request fallback to a different *provider* (Gemini, using the key
    already in .env) was tried and reverted: it doesn't fail fast on a bad
    call, it hangs for minutes past its own timeout parameter before ever
    raising - confirmed by direct testing. That's worse than the honest
    static fallback content the caller already returns on total failure, so
    it's not a usable fallback with our pinned litellm version.

    Returns a plain model string by default (proven reliable for the Web
    Search Agent's summary). Only pass max_tokens for an agent that's
    specifically running out of room - we found that raising the default
    for every agent made this model MORE likely to ramble through a visible
    chain-of-thought instead of answering directly, not less, so don't
    apply it globally.
    """
    model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
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


def kickoff_with_fallback(build_crew):
    """Run a CrewAI crew built against the primary model; on a rate limit,
    switch to FALLBACK_MODEL immediately (no wait - it's a separate quota
    bucket, so there's nothing to wait out) instead of retrying the same
    exhausted model. Only if the fallback is *also* rate limited does this
    fall back to waiting out that model's own suggested cooldown as a last
    resort.

    `build_crew` is a callable(model: str) -> Crew, not a pre-built Crew -
    switching models means rebuilding the Agent with a different `llm`, so
    the caller needs to hand over a builder rather than a finished crew.

    This is the actual fix for the shared-team-quota problem: retrying the
    same model (the previous behavior) does nothing once that model's whole
    per-minute budget is gone, since every retry lands in the same exhausted
    bucket. A second Groq model has its own separate budget, so switching to
    it is real, immediate headroom rather than a longer wait for the same
    wall to still be there.
    """
    primary = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    fallback = os.environ.get("LLM_FALLBACK_MODEL", FALLBACK_MODEL)
    models = [primary] if primary == fallback else [primary, fallback]

    last_exc = None
    for i, model in enumerate(models):
        try:
            return build_crew(model).kickoff()
        except Exception as exc:
            last_exc = exc
            wait = _retry_after_seconds(exc)
            if wait is None:
                raise

            is_last = i == len(models) - 1
            if not is_last:
                logger.warning(
                    "Rate limited on %s, switching to fallback model %s instead of waiting %.1fs",
                    model, models[i + 1], wait,
                )
                continue

            wait = min(wait, _MAX_RETRY_WAIT_SECONDS) + 0.5
            logger.warning("All models rate limited, waiting %.1fs before one final retry", wait)
            time.sleep(wait)
            return build_crew(model).kickoff()
    raise last_exc
