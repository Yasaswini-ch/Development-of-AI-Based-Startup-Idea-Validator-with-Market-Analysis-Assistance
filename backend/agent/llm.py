import logging
import os
import re
import threading
import time

from crewai import LLM

from . import events

logger = logging.getLogger(__name__)

# Track G.2 - caps how many LLM calls run at once across the whole process,
# regardless of which of the 3 fallback models/providers they land on. Each
# pipeline run makes up to 4 sequential calls (market/swot/mvp/gtm) already,
# so the real risk here is concurrent *requests* (several founders
# validating at once) all hitting the same shared Groq quota simultaneously
# - a semaphore in front of the one shared entry point (_kickoff_with_metrics)
# throttles that without needing every caller to coordinate. A plain
# threading.Semaphore (not asyncio) since crew.kickoff() is a blocking call
# made from a sync function either way, on whatever thread FastAPI happens
# to run the request/background task on.
_MAX_CONCURRENT_LLM_CALLS = int(os.environ.get("MAX_CONCURRENT_LLM_CALLS", "4"))
_llm_semaphore = threading.Semaphore(_MAX_CONCURRENT_LLM_CALLS)

# qwen3.6-27b was deprecated and removed from Groq (confirmed via
# GET /openai/v1/models on Sept 15, 2026: only qwen/qwen3.8-27b remains of the
# qwen line). qwen3.8-27b was confirmed live against our key, including
# accepting reasoning_effort="none" with the same 2-token "say OK" behavior
# the quota fix below was validated against.
DEFAULT_MODEL = "groq/qwen/qwen3.8-27b"

# Track F end-to-end pass: no per-call timeout was set anywhere in this
# file - a genuinely slow (not rate-limited, not erroring) provider
# response had nothing bounding it, unlike kickoff_with_fallback's own
# rate-limit retry wait (_MAX_RETRY_WAIT_SECONDS below). 30s per attempt
# keeps real Groq/Gemini calls (confirmed live at well under 2s - see
# get_llm's docstring) comfortably clear of any false-positive timeout,
# while still bounding the worst case: main.py's own
# VALIDATE_ASYNC_THRESHOLD_SECONDS (default 60s) already treats a /validate
# request over a minute as needing the async/email path, so a single stuck
# call capped well under that keeps the synchronous path from hanging past
# what the rest of the system already assumes is possible.
_LLM_CALL_TIMEOUT_SECONDS = float(os.environ.get("LLM_CALL_TIMEOUT_SECONDS", "30"))

# Two models hosted on the *same* Groq account, each with its own rate-limit
# bucket - confirmed via `GET /openai/v1/models` against our own key and a
# direct latency test (all respond in under a second). In practice, active
# testing exhausted both Groq tiers' buckets in the same session (they're
# separate 8000 TPM pools, but heavy back-to-back traffic burns through both),
# so a third tier on a wholly separate provider/quota - Gemini, on the key
# already in .env - is the real fix for "every model I can reach shares one
# account's budget." See get_llm's docstring for why this was previously
# reverted and why the retest changed that.
FALLBACK_MODELS = ("groq/openai/gpt-oss-20b", "groq/openai/gpt-oss-120b", "gemini/gemini-3.6-flash")
_MAX_RETRY_WAIT_SECONDS = 30

# Last-resort tier, tried only when a caller opts in via
# kickoff_with_fallback(..., allow_local=True) - i.e. only once an email is
# on file to send the (slower) result to, since local inference on
# consumer hardware genuinely takes minutes, not seconds. Runs through
# Ollama (confirmed installed locally with this model pulled) rather than a
# fourth cloud quota, so it has zero dependency on any provider's rate
# limits - the whole point is a tier that's never "also exhausted."
LOCAL_MODEL = os.environ.get("LOCAL_LLM_MODEL", "ollama/qwen2.5:7b")
_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# Confirmed via manual timing: a 7b model on typical dev hardware can take
# well over a minute per call, several times _LLM_CALL_TIMEOUT_SECONDS'
# 30s cloud budget - this tier needs its own, much longer ceiling rather
# than inheriting the cloud one and failing before local inference even
# finishes a single call.
_LOCAL_LLM_TIMEOUT_SECONDS = float(os.environ.get("LOCAL_LLM_TIMEOUT_SECONDS", "240"))


class NeedsDeepAnalysisError(Exception):
    """Raised by kickoff_with_fallback (allow_local=False) when every cloud
    model is exhausted, and by each analyze_* agent when its output still
    doesn't parse even after that - the signal that this request's result
    would otherwise be the deterministic fallback wearing a "degraded" flag
    nobody asked to see. Callers with an email on file retry with
    allow_local=True instead of catching this; graph.py's nodes catch it
    from callers that don't (no email yet) and short-circuit the whole
    pipeline via state["error"], so main.py can ask for an email up front
    instead of silently serving the weaker result.
    """

# The actual cause of most "Request too large... exceeds the enforced limit"
# failures all session: by default, qwen3.6-27b reserves an output-token
# budget for its own hidden <think> reasoning that alone exceeds Groq's 1000
# output-tokens-per-minute cap - confirmed directly: the same trivial "say
# OK" prompt failed outright with reasoning left at its default, and
# succeeded using 2 completion tokens with reasoning_effort="none". Real
# agent calls (market/competitor analysis) confirmed the same fix end to
# end: fewer real failures, and the tokens actually used drop sharply since
# there's no wasted scratchpad to generate or strip.
#
# Each model takes a different set of valid values (also confirmed
# directly, not assumed) - qwen3.6-27b accepts "none" or "default";
# openai/gpt-oss-20b and -120b reject "none" outright and require one of
# "low"/"medium"/"high", so "low" is the closest equivalent for those.
# (qwen3.6-27b's "none" entry was dropped with the model itself - see
# DEFAULT_MODEL above; qwen3.8-27b was confirmed to accept "none" live.)
# gemini-3.6-flash hits the exact same failure shape as qwen did: left at
# its default, it spends its entire max_tokens budget on hidden reasoning
# and returns empty content (finish_reason="length", 0 text tokens) -
# confirmed live, and "none" fixes it the same way, down to a 1-token reply.
_REASONING_EFFORT = {
    "groq/qwen/qwen3.8-27b": "none",
    "groq/openai/gpt-oss-20b": "low",
    "groq/openai/gpt-oss-120b": "low",
    "gemini/gemini-3.6-flash": "none",
}


def get_llm(max_tokens: int | None = None, model: str | None = None):
    """LLM used by every CrewAI agent, via LiteLLM.

    Set LLM_MODEL to override the primary model, LLM_FALLBACK_MODELS
    (comma-separated) to override the fallback chain (see FALLBACK_MODELS
    above and kickoff_with_fallback). Groq needs GROQ_API_KEY, Gemini needs
    GEMINI_API_KEY.

    A same-request fallback to a different *provider* (Gemini) was
    previously tried and reverted here as "hangs for minutes past its own
    timeout." Retested directly against litellm 1.97.0 on 2026-09-20: no
    hang - every call returned or raised in under 2s, timeouts included.
    What actually looked like a hang before was two separate issues that
    both fail in an unrelated-looking way: (1) the model name on file then
    (gemini-1.5-flash / gemini-2.0-flash) is deprecated and now 404s
    instantly rather than hanging, and (2) gemini-3.6-flash, like
    qwen3.8-27b, spends its whole max_tokens budget on hidden reasoning and
    returns empty content unless reasoning_effort="none" - a fast,
    silent-looking failure, not a slow one. With the current model name and
    that fix applied, Gemini is a genuine third fallback tier on a wholly
    separate quota pool from Groq - see FALLBACK_MODELS.

    Always returns an `LLM` object, never a plain model string - every call
    gets _LLM_CALL_TIMEOUT_SECONDS applied (override with
    LLM_CALL_TIMEOUT_SECONDS) regardless of whether max_tokens or a known
    reasoning_effort also apply, and the model's known-good reasoning_effort
    is added on top whenever the model is one of the ones in
    _REASONING_EFFORT above; an unrecognized model (e.g. a manual LLM_MODEL
    override) just skips that one kwarg rather than getting a
    reasoning_effort value it was never confirmed to accept.
    """
    model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    is_local = model.startswith("ollama/")
    kwargs = {"timeout": _LOCAL_LLM_TIMEOUT_SECONDS if is_local else _LLM_CALL_TIMEOUT_SECONDS}
    if is_local:
        kwargs["api_base"] = _OLLAMA_BASE_URL
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    reasoning_effort = _REASONING_EFFORT.get(model)
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    return LLM(model=model, **kwargs)


def _is_model_not_found_error(exc: Exception) -> bool:
    """True when the model itself doesn't exist / isn't accessible (Groq code
    "model_not_found"). Found live on Sept 15, 2026: the then-primary
    qwen/qwen3.6-27b was deprecated out from under a deployed config, and this
    404-shaped failure was raised straight through kickoff_with_fallback
    instead of trying the fallback models - even though they were perfectly
    healthy and on completely separate quota buckets. A missing model is at
    least as switch-worthy as an exhausted one: waiting can't fix it, but the
    next model can.
    """
    text = str(exc)
    return "model_not_found" in text or "does not exist or you do not have access" in text


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


def _kickoff_with_metrics(model: str, build_crew):
    """Runs one crew.kickoff() call and logs latency + token usage - the
    real numbers Track F's optimization pass needs to tune prompt/limit
    budgets from, which nothing previously captured (only success/failure
    was logged, never how long a call took or how many tokens it used).

    Gated by _llm_semaphore (Track G.2) so at most MAX_CONCURRENT_LLM_CALLS
    real network calls are in flight at once, across every concurrent
    request this process is handling - acquired here rather than around the
    whole kickoff_with_fallback loop, so a wait for a slot doesn't also
    count against _MAX_RETRY_WAIT_SECONDS' cooldown wait, which is a
    different kind of backoff (provider-told, not our own concurrency cap).
    """
    with _llm_semaphore:
        start = time.time()
        output = build_crew(model).kickoff()
    elapsed_ms = round((time.time() - start) * 1000)
    usage = getattr(output, "token_usage", None)
    if usage is not None:
        logger.info(
            "llm_call model=%s elapsed_ms=%d prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            model, elapsed_ms,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            getattr(usage, "total_tokens", None),
        )
    else:
        logger.info("llm_call model=%s elapsed_ms=%d", model, elapsed_ms)
    # Durable counterpart to the log line above - GET /admin/platform-metrics'
    # "Groq Model Usage" split reads this. Only reached on success (an
    # exception from build_crew(model).kickoff() propagates straight out of
    # this function), so this is exactly "which model actually served the
    # call," not every model merely attempted.
    events.record("model_used", detail={"model": model, "elapsedMs": elapsed_ms})
    return output


def kickoff_with_fallback(build_crew, primary: str | None = None, allow_local: bool = False, validate=None):
    """Run a CrewAI crew against the cloud fallback chain; when every cloud
    model is exhausted, either raise NeedsDeepAnalysisError (allow_local
    False - the default, used on a request's first attempt before an email
    address is known) or try LOCAL_MODEL as one final attempt (allow_local
    True - only once an email is on file, since this can take minutes).
    See NeedsDeepAnalysisError's docstring for the full flow.

    `validate`, if given, is called with the raw CrewOutput and should
    return True for a usable response. A cloud model that responds but
    fails validation (e.g. no parseable JSON in the expected shape) is
    treated the same as a cloud model that errored outright - it's just as
    much a "wrong result" as a rate limit, so it gets the same local-model
    retry (or the same NeedsDeepAnalysisError signal) rather than silently
    reaching the caller's own except-block and going straight to the
    deterministic fallback without ever trying the local model.
    """
    try:
        output = _kickoff_cloud_chain(build_crew, primary)
        if validate is not None and not validate(output):
            raise ValueError("Cloud model response failed validation (unparseable or wrong shape).")
        return output
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning("Cloud path exhausted or invalid, trying local model %s", LOCAL_MODEL)
        return _kickoff_with_metrics(LOCAL_MODEL, build_crew)


def _kickoff_cloud_chain(build_crew, primary: str | None = None):
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

    `primary` overrides the usual LLM_MODEL/DEFAULT_MODEL choice for just
    this call, without changing what every other caller defaults to. Used
    by chat_graph.py so the chat advisor - the most frequently-hit endpoint
    during interactive use - defaults to Gemini's separate quota pool
    instead of competing with the five pipeline analysis agents for the
    same Groq budget on every session; it still falls through to the Groq
    models below if Gemini itself is unavailable.
    """
    primary = primary or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    fallbacks_env = os.environ.get("LLM_FALLBACK_MODELS")
    fallbacks = [m.strip() for m in fallbacks_env.split(",")] if fallbacks_env else list(FALLBACK_MODELS)

    models = [primary]
    for m in fallbacks:
        if m not in models:
            models.append(m)

    last_exc = None
    for i, model in enumerate(models):
        try:
            return _kickoff_with_metrics(model, build_crew)
        except Exception as exc:
            last_exc = exc
            # model_not_found switches immediately too (see
            # _is_model_not_found_error) - but only ever waits out a cooldown
            # for an actual rate limit, since no wait fixes a missing model.
            if not (_is_rate_limit_error(exc) or _is_model_not_found_error(exc)):
                raise

            is_last = i == len(models) - 1
            if not is_last:
                reason = (
                    "Rate limited" if _is_rate_limit_error(exc)
                    else "Model unavailable"
                )
                logger.warning(
                    "%s on %s, switching to fallback model %s",
                    reason, model, models[i + 1],
                )
                continue

            # Every model in the chain is exhausted or unavailable. Only wait
            # if this last failure is a rate limit that actually names a
            # cooldown - if it's the "requested output exceeds the model's own
            # per-minute cap" shape, or the model simply doesn't exist, no
            # wait fixes that, so there's nothing left to do but report the
            # failure.
            if not _is_rate_limit_error(exc):
                raise
            wait = _retry_after_seconds(exc)
            if wait is None:
                raise

            wait = min(wait, _MAX_RETRY_WAIT_SECONDS) + 0.5
            logger.warning("All models rate limited, waiting %.1fs before one final retry", wait)
            time.sleep(wait)
            return _kickoff_with_metrics(model, build_crew)
    raise last_exc
