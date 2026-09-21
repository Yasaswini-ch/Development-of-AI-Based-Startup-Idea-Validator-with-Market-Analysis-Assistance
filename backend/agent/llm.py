# ============================================================
# agent/llm.py
# ============================================================

import logging
import os
import re
import time
from typing import Callable, Any

from dotenv import load_dotenv
from crewai import LLM
from litellm import completion


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

DEFAULT_MODEL = os.getenv(
    "LLM_MODEL",
    "groq/openai/gpt-oss-120b",
).strip()


DEFAULT_FALLBACK_MODELS = (
    "groq/openai/gpt-oss-20b",
    "groq/qwen/qwen3.8-27b",
)


def _read_fallback_models() -> tuple[str, ...]:
    raw = os.getenv(
        "LLM_FALLBACK_MODELS",
        "",
    ).strip()

    if not raw:
        return DEFAULT_FALLBACK_MODELS

    models = []

    for item in raw.split(","):
        model = item.strip()

        if model and model not in models:
            models.append(model)

    return tuple(models)


FALLBACK_MODELS = _read_fallback_models()


# ============================================================
# MODEL CHAIN
# ============================================================

def _build_model_chain() -> list[str]:

    models = [
        DEFAULT_MODEL,
        *FALLBACK_MODELS,
    ]

    result = []

    for model in models:

        model = model.strip()

        if not model:
            continue

        if model not in result:
            result.append(model)

    return result


_MODEL_CHAIN = _build_model_chain()


def get_model_chain() -> list[str]:
    return list(_MODEL_CHAIN)


# ============================================================
# REASONING CONFIGURATION
# ============================================================

_REASONING_EFFORT = {
    "groq/openai/gpt-oss-120b": "low",
    "groq/openai/gpt-oss-20b": "low",
    "groq/qwen/qwen3.8-27b": "none",
}


# ============================================================
# RETRY CONFIGURATION
# ============================================================

_MAX_RETRY_WAIT_SECONDS = int(
    os.getenv(
        "LLM_MAX_RETRY_WAIT_SECONDS",
        "8",
    )
)

_MAX_ATTEMPTS_PER_MODEL = 1


# ============================================================
# ERROR DETECTION
# ============================================================

def _is_rate_limit_error(exc: Exception) -> bool:

    text = str(exc).lower()

    patterns = (
        "ratelimit",
        "rate limit",
        "rate_limit",
        "too many requests",
        "429",
        "tokens per minute",
        "output tokens per minute",
        "otpm",
        "tpm limit",
    )

    return any(
        pattern in text
        for pattern in patterns
    )


def _is_model_not_found_error(
    exc: Exception,
) -> bool:

    text = str(exc).lower()

    patterns = (
        "model not found",
        "model_not_found",
        "unknown model",
        "does not exist",
        "not available",
        "invalid model",
    )

    return any(
        pattern in text
        for pattern in patterns
    )


# ============================================================
# RETRY-AFTER
# ============================================================

def _retry_after_seconds(
    exc: Exception,
) -> float | None:

    text = str(exc)

    patterns = (
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retry[- ]after[:\s]+([0-9]+(?:\.[0-9]+)?)",
        r"reset[- ]tokens[:\s]+([0-9]+(?:\.[0-9]+)?)s",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            try:
                return float(
                    match.group(1)
                )

            except ValueError:
                pass

    return None


# ============================================================
# MODEL NORMALIZATION
# ============================================================

def _normalize_model(model: str) -> str:
    """
    CrewAI's LLM class works best when the provider/model
    information is explicitly preserved.

    Example:
        groq/openai/gpt-oss-120b
    """

    return model.strip()


# ============================================================
# CREWAI LLM FACTORY
# ============================================================

def get_llm(
    max_tokens: int = 500,
    model: str | None = None,
):
    """
    Return a CrewAI-compatible LLM object.

    This function is used by:

        Agent(llm=get_llm(...))

    Therefore it MUST return a CrewAI LLM instance,
    not a custom wrapper object.
    """

    selected_model = _normalize_model(
        model or DEFAULT_MODEL
    )

    reasoning_effort = _REASONING_EFFORT.get(
        selected_model,
        "low",
    )

    logger.info(
        "Creating CrewAI LLM | model=%s | max_tokens=%d | reasoning=%s",
        selected_model,
        max_tokens,
        reasoning_effort,
    )

    # --------------------------------------------------------
    # IMPORTANT
    # --------------------------------------------------------
    # CrewAI internally calls LiteLLM.
    #
    # Passing a CrewAI LLM object prevents the previous error:
    #
    # model=<agent.llm.get_llm.<locals>.LLMWrapper object>
    #
    # --------------------------------------------------------

    return LLM(
        model=selected_model,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )


# ============================================================
# DIRECT LITELLM CALL
# ============================================================

def call_llm(
    messages,
    max_tokens: int = 500,
    model: str | None = None,
):
    """
    Direct LiteLLM call for agents that do NOT use CrewAI.

    Returns the raw LiteLLM response.
    """

    selected_model = _normalize_model(
        model or DEFAULT_MODEL
    )

    reasoning_effort = _REASONING_EFFORT.get(
        selected_model,
        "low",
    )

    start = time.time()

    try:

        response = completion(
            model=selected_model,
            messages=messages,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )

        elapsed_ms = round(
            (time.time() - start) * 1000
        )

        usage = getattr(
            response,
            "usage",
            None,
        )

        prompt_tokens = int(
            getattr(
                usage,
                "prompt_tokens",
                0,
            )
            or 0
        )

        completion_tokens = int(
            getattr(
                usage,
                "completion_tokens",
                0,
            )
            or 0
        )

        total_tokens = int(
            getattr(
                usage,
                "total_tokens",
                0,
            )
            or 0
        )

        logger.info(
            "llm_call model=%s "
            "elapsed_ms=%d "
            "prompt_tokens=%d "
            "completion_tokens=%d "
            "total_tokens=%d",
            selected_model,
            elapsed_ms,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )

        return response

    except Exception:

        elapsed_ms = round(
            (time.time() - start) * 1000
        )

        logger.warning(
            "llm_call_failed model=%s elapsed_ms=%d",
            selected_model,
            elapsed_ms,
        )

        raise


# ============================================================
# DIRECT LLM WITH FALLBACK
# ============================================================

def call_llm_with_fallback(
    messages,
    max_tokens: int = 500,
):
    """
    Direct LiteLLM call with model fallback.

    Used by agents such as market_agent that do not
    use CrewAI's Agent class.
    """

    last_error = None

    for index, model in enumerate(
        get_model_chain(),
        start=1,
    ):

        logger.info(
            "Direct LLM attempt %d/%d: %s",
            index,
            len(_MODEL_CHAIN),
            model,
        )

        try:

            return call_llm(
                messages=messages,
                max_tokens=max_tokens,
                model=model,
            )

        except Exception as exc:

            last_error = exc

            if _is_rate_limit_error(exc):

                logger.warning(
                    "Model %s is rate limited; "
                    "switching to next model",
                    model,
                )

                continue

            if _is_model_not_found_error(exc):

                logger.warning(
                    "Model %s unavailable; "
                    "switching to next model",
                    model,
                )

                continue

            logger.warning(
                "Model %s failed; switching to next model: %s",
                model,
                exc,
            )

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "No LLM models were available."
    )


# ============================================================
# MODEL CONFIGURATION LOG
# ============================================================

def log_model_configuration() -> None:

    logger.info(
        "LLM model chain: %s",
        " -> ".join(
            _MODEL_CHAIN
        ),
    )

    for model in _MODEL_CHAIN:

        logger.info(
            "LLM reasoning effort | model=%s | effort=%s",
            model,
            _REASONING_EFFORT.get(
                model,
                "low",
            ),
        )


# ============================================================
# CREWAI KICKOFF WITH FALLBACK
# ============================================================

def kickoff_with_fallback(
    crew_factory: Callable[[str], Any],
):
    """
    Execute a CrewAI crew using the configured model chain.

    crew_factory(model) must create the CrewAI crew using:

        get_llm(model=model)

    Rate-limited models are skipped immediately.
    """

    last_error = None

    models = get_model_chain()

    logger.info(
        "LLM model chain: %s",
        " -> ".join(models),
    )

    for index, model in enumerate(
        models,
        start=1,
    ):

        logger.info(
            "Attempting LLM model %d/%d: %s",
            index,
            len(models),
            model,
        )

        start = time.time()

        try:

            crew = crew_factory(
                model
            )

            result = crew.kickoff()

            elapsed_ms = round(
                (time.time() - start) * 1000
            )

            logger.info(
                "LLM model succeeded: %s elapsed_ms=%d",
                model,
                elapsed_ms,
            )

            return result

        except Exception as exc:

            last_error = exc

            elapsed_ms = round(
                (time.time() - start) * 1000
            )

            logger.warning(
                "LLM model failed: %s "
                "elapsed_ms=%d "
                "error=%s",
                model,
                elapsed_ms,
                str(exc),
            )

            if _is_rate_limit_error(exc):

                logger.warning(
                    "Model %s is rate limited; "
                    "switching to next model",
                    model,
                )

                retry_after = _retry_after_seconds(
                    exc
                )

                if (
                    retry_after is not None
                    and retry_after <= 0.5
                ):

                    time.sleep(
                        min(
                            retry_after,
                            _MAX_RETRY_WAIT_SECONDS,
                        )
                    )

                continue

            if _is_model_not_found_error(exc):

                logger.warning(
                    "Model %s is unavailable; "
                    "switching to next model",
                    model,
                )

                continue

            # Other errors also move to next model.
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "No LLM models were available."
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "DEFAULT_MODEL",
    "FALLBACK_MODELS",
    "get_llm",
    "call_llm",
    "call_llm_with_fallback",
    "get_model_chain",
    "log_model_configuration",
    "kickoff_with_fallback",
]