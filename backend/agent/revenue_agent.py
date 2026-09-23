"""Suggests 2-3 revenue models matched to the specific market and customer.

Runs after market_opportunity and competitor_discovery so it can ground
each model in the actual segment and competitive evidence already collected.
No new API calls — input is the already-gathered pipeline artifacts only.
"""

import logging

from crewai import Agent, Crew, Process, Task

from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback
from .prompts.loader import load_prompt
from .structured_output import (
    compact_json,
    compact_sources,
    extract_json_object,
    sanitize_source_ids,
    valid_source_ids,
)

logger = logging.getLogger(__name__)

_FIT_SCORES = {"high", "medium", "low"}
_MAX_MODELS = 3


def _valid_model(item) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item.get("name").strip()
        and item.get("fit") in _FIT_SCORES
        and isinstance(item.get("rationale"), str)
        and item.get("rationale").strip()
        and isinstance(item.get("tradeoffs"), str)
        and item.get("tradeoffs").strip()
        and valid_source_ids(item.get("sourceIds", []))
    )


def _valid_shape(value: dict) -> bool:
    models = value.get("models")
    if not isinstance(models, list) or not models:
        return False
    return all(_valid_model(item) for item in models)


def _build_crew(
    idea: str,
    target_customer: str,
    context: str,
    model: str,
) -> Crew:
    analyst = Agent(
        role="Monetization Strategist",
        goal="Match revenue models to the specific market dynamics and customer behavior already evidenced.",
        backstory=load_prompt("revenue_system"),
        llm=get_llm(max_tokens=450, model=model),
        verbose=False,
    )
    task = Task(
        description=load_prompt(
            "revenue_task",
            idea=idea,
            target_customer=target_customer or "not specified",
            context=context,
        ),
        expected_output=load_prompt("revenue_output"),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_revenue_models(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    results: list,
    allow_local: bool = False,
) -> dict:
    sources = compact_sources(results)
    valid_ids = {source["sourceId"] for source in sources}
    context = compact_json(
        {
            "segments": (market_opportunity or {}).get("segments", [])[:3],
            "competitors": (competitors or {}).get("competitors", [])[:4],
            "sources": sources,
        },
        max_chars=2800,
    )
    try:
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, target_customer, context, model),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("Revenue agent returned no valid JSON")
            raise ValueError("Revenue model analysis did not return a valid result.")
        data["models"] = [
            {**item, "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["models"][:_MAX_MODELS]
        ]
        return data
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "Revenue agent: LLM unavailable, returning empty models",
            exc_info=True,
        )
        return {"models": [], "degraded": True}
