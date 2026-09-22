"""MVP feature recommendations grounded in SWOT and customer evidence."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_mvp
from .llm import get_llm, kickoff_with_fallback
from .prompts.loader import load_prompt
from .structured_output import (
    compact_json,
    compact_sources,
    extract_json_object,
    sanitize_source_ids,
    valid_source_ids,
)

logger = logging.getLogger(__name__)

_LEVELS = {"low", "medium", "high", "unknown"}
_MAX_FEATURES = 5


def _valid_shape(value: dict) -> bool:
    features = value.get("features")
    if not isinstance(features, list) or not features:
        return False
    return all(
        isinstance(item, dict)
        and isinstance(item.get("feature"), str)
        and isinstance(item.get("rationale"), str)
        and item.get("impact") in _LEVELS
        and item.get("effort") in _LEVELS
        and valid_source_ids(item.get("sourceIds", []))
        for item in features
    )


def _build_crew(idea: str, problem: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="MVP Feature Recommendation Analyst",
        goal="Prioritize the smallest feature set that tests the startup's riskiest assumptions.",
        backstory=load_prompt("mvp_system"),
        # Rebalanced to 450 (was 800, briefly tried 250) - see
        # market_agent.py for the full rationale; 250 was confirmed live to
        # truncate JSON output itself, not just hit the rate limit.
        llm=get_llm(max_tokens=450, model=model),
        verbose=False,
    )
    task = Task(
        description=load_prompt("mvp_task", idea=idea, problem=problem or "not specified", context=context),
        expected_output=load_prompt("mvp_output"),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_mvp(
    idea: str,
    problem: str,
    swot: dict | None,
    market_opportunity: dict | None,
    results: list,
) -> dict:
    sources = compact_sources(results)
    valid_ids = {source["sourceId"] for source in sources}
    context = compact_json(
        {
            "swot": swot,
            "segments": (market_opportunity or {}).get("segments", [])[:4],
            "sources": sources,
        },
        max_chars=3500,
    )
    try:
        output = kickoff_with_fallback(lambda model: _build_crew(idea, problem, context, model))
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("MVP agent returned no valid JSON")
            raise ValueError("MVP analysis did not return a valid result.")
        data["features"] = [
            {**item, "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["features"][:_MAX_FEATURES]
        ]
        return data
    except Exception:
        logger.warning(
            "MVP: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_mvp(idea, problem, swot, market_opportunity)
