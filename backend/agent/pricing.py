"""Per-model token prices for the Platform Health "Tokens & cost" charts.

Cost is estimated here from the token counts each LLM call already reports
(llm.py's _kickoff_with_metrics) times a list price - no provider exposes a
per-request bill, so this is an estimate by construction and the dashboard
labels it that way.

Groq prices match docs/13_AFFINITY_UNIT_ECONOMICS_COST_AND_ACCURACY_METRICS.md.
The Gemini flash tiers use Google's published flash-class list price as an
assumption (the repo documents no price for them). Local Ollama inference
has no per-token bill. Any entry can be overridden without a deploy via the
LLM_PRICING_JSON env var, e.g.
  {"gemini/gemini-3.6-flash": {"input": 0.3, "output": 2.5}}
with prices in USD per 1M tokens.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# USD per 1M tokens.
_DEFAULT_PRICES = {
    "groq/qwen/qwen3.8-27b": {"input": 0.29, "output": 0.59},
    "groq/openai/gpt-oss-20b": {"input": 0.15, "output": 0.60},
    "groq/openai/gpt-oss-120b": {"input": 0.59, "output": 1.18},
    "gemini/gemini-3.6-flash": {"input": 0.30, "output": 2.50},
    "gemini/gemini-3.8-flash": {"input": 0.30, "output": 2.50},
}


def _load_prices() -> dict:
    prices = dict(_DEFAULT_PRICES)
    raw = os.environ.get("LLM_PRICING_JSON")
    if raw:
        try:
            prices.update(json.loads(raw))
        except (ValueError, TypeError):
            logger.warning("LLM_PRICING_JSON is not valid JSON - using default prices")
    return prices


PRICES = _load_prices()


def estimate_cost_usd(model: str, prompt_tokens: int | None, completion_tokens: int | None) -> float:
    """Estimated USD cost of one call. Unknown and local models cost 0."""
    price = PRICES.get(model)
    if not price:
        return 0.0
    return ((prompt_tokens or 0) * price["input"] + (completion_tokens or 0) * price["output"]) / 1_000_000


__all__ = ["PRICES", "estimate_cost_usd"]
