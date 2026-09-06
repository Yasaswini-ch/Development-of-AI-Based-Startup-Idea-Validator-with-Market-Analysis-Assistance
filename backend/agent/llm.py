import logging
import os
import re
import time

from crewai import LLM

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "groq/qwen/qwen3.6-27b"

# More models hosted on the *same* Groq account, each with its own rate-limit
# bucket - confirmed via `GET /openai/v1/models` against our own key and a
# direct latency test (all respond in under a second, nothing like Gemini's
# multi-minute hang, see kickoff_with_fallback's docstring). Two fallbacks
# rather than one: in practice, active testing (this session's plus the
# team's) exhausted a single fallback's bucket at the same time as the
# primary's, so one extra tier of real headroom matters, not just one.
FALLBACK_MODELS = ("groq/openai/gpt-oss-20b", "groq/openai/gpt-oss-120b")
_MAX_RETRY_WAIT_SECONDS = 30


def get_llm(max_tokens: int | None = None, model: str | None = None):
    """LLM used by every CrewAI agent, via LiteLLM.

    Set LLM_MODEL to override the primary model, LLM_FALLBACK_MODELS
    (comma-separated) to override the fallback chain (see FALLBACK_MODELS
    above and kickoff_with_fallback). Groq needs GROQ_API_KEY.

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


def _is_rate_limit_error(exc: Exception) -> bool:
    """True for any Groq rate-limit response, whether or not it names a
    concrete cooldown. Groq has (at least) two differently-shaped rate-limit
    errors: "Used 980/1000, try again in 6.2s" (a real cooldown to wait out)
    and "Requested 2048, limit is 1000" (a single request's own configured
    output cap exceeds the model's entire per-minute budget - no amount of
    waiting fixes that on this model, only a different model can). Both
    carry Groq's own "rate_limit_exceeded" code, so checking for that -
    instead of requiring the "try again in Ns" phrase - is what actually
    catches both, confirmed live: the second shape was silently treated as
    unrecoverable before this fix, raising immediately instead of trying the
    next model, even though the next model doesn't share that request's
    conflict with the first one's tighter per-minute cap.
    """
    text = str(exc)
    return "rate_limit_exceeded" in text or "RateLimitError" in text


def _retry_after_seconds(exc: Exception) -> float | None:
    """Groq's rate-limit error message sometimes names its own cooldown,
    e.g. "Please try again in 25.545s" - parse that instead of guessing a
    backoff. Returns None when no concrete cooldown is present (see
    _is_rate_limit_error - that's still a rate limit, just not one where
    waiting would help).
    """
    match = re.search(r"try again in ([\d.]+)s", str(exc))
    return float(match.group(1)) if match else None


def kickoff_with_fallback(build_crew):
    """Run a CrewAI crew built against the primary model; on a rate limit,
    switch to the next model in FALLBACK_MODELS immediately (no wait - each
    is a separate quota bucket, so there's nothing to wait out) instead of
    retrying the same exhausted model. Only once every model in the chain
    has been rate limited does this fall back to waiting out the last one's
    own suggested cooldown, as a final resort.

    `build_crew` is a callable(model: str) -> Crew, not a pre-built Crew -
    switching models means rebuilding the Agent with a different `llm`, so
    the caller needs to hand over a builder rather than a finished crew.

    This is the actual fix for the shared-team-quota problem: retrying the
    same model (the previous behavior) does nothing once that model's whole
    per-minute budget is gone, since every retry lands in the same exhausted
    bucket. Each additional Groq model here is its own separate budget, so
    switching to one is real, immediate headroom rather than a longer wait
    for the same wall to still be there.
    """
    primary = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    fallbacks_env = os.environ.get("LLM_FALLBACK_MODELS")
    fallbacks = [m.strip() for m in fallbacks_env.split(",")] if fallbacks_env else list(FALLBACK_MODELS)

    models = [primary]
    for m in fallbacks:
        if m not in models:
            models.append(m)

    last_exc = None
    for i, model in enumerate(models):
        try:
            return build_crew(model).kickoff()
        except Exception as exc:
            last_exc = exc
            if not _is_rate_limit_error(exc):
                raise

            is_last = i == len(models) - 1
            if not is_last:
                logger.warning(
                    "Rate limited on %s, switching to fallback model %s",
                    model, models[i + 1],
                )
                continue

            # Every model in the chain is rate limited. Only wait if this
            # last failure actually names a cooldown - if it's the
            # "requested output exceeds the model's own per-minute cap"
            # shape instead, no wait fixes that on this same model, so
            # there's nothing left to do but report the failure.
            wait = _retry_after_seconds(exc)
            if wait is None:
                raise

            wait = min(wait, _MAX_RETRY_WAIT_SECONDS) + 0.5
            logger.warning("All models rate limited, waiting %.1fs before one final retry", wait)
            time.sleep(wait)
            return build_crew(model).kickoff()
    raise last_exc
