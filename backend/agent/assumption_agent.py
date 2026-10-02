"""Surfaces the riskiest hidden assumptions the analysis rests on.

Each assumption is ranked by uncertainty and paired with a concrete
"howToValidate" step — the primary output the founder acts on.
No API enrichment: input is the already-collected SWOT, market, and
MVP artifacts only, so this runs after those nodes with no extra quota.
"""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_assumptions
from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback, primary_for, AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER
from .prompts.loader import load_prompt
from .structured_output import (
    compact_json,
    compact_sources,
    extract_json_object,
    sanitize_source_ids,
    valid_source_ids,
)

logger = logging.getLogger(__name__)

_CATEGORIES = {"demand", "market", "technical", "competitive", "regulatory"}
_UNCERTAINTIES = {"high", "medium", "low"}
_MAX_ASSUMPTIONS = 5


def _valid_assumption(item) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("assumption"), str)
        and item.get("assumption").strip()
        and item.get("category") in _CATEGORIES
        and item.get("uncertainty") in _UNCERTAINTIES
        and isinstance(item.get("howToValidate"), str)
        and item.get("howToValidate").strip()
        # riskIfWrong and timeToValidate are optional for backward compatibility
        and (item.get("riskIfWrong") is None or isinstance(item.get("riskIfWrong"), str))
        and (item.get("timeToValidate") is None or isinstance(item.get("timeToValidate"), str))
        and valid_source_ids(item.get("sourceIds", []))
    )


def _normalize_assumption(item):
    """Models often capitalise enum values ("High", "Demand"); lower-case
    them so one cosmetic slip doesn't reject an otherwise valid answer."""
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    for field in ("category", "uncertainty"):
        if isinstance(normalized.get(field), str):
            normalized[field] = normalized[field].strip().lower()
    return normalized


def _usable_assumptions(value: dict) -> list:
    assumptions = value.get("assumptions")
    if not isinstance(assumptions, list):
        return []
    return [item for item in map(_normalize_assumption, assumptions) if _valid_assumption(item)]


def _valid_shape(value: dict) -> bool:
    # Accept the answer when at least one assumption is valid; the invalid
    # ones are dropped below instead of discarding the whole response.
    return bool(_usable_assumptions(value))


def _build_crew(
    idea: str,
    target_customer: str,
    problem: str,
    context: str,
    model: str,
) -> Crew:
    analyst = Agent(
        role="Startup Assumption Analyst",
        goal="Identify and rank the riskiest hidden assumptions a startup plan rests on.",
        backstory=load_prompt("assumption_system"),
        llm=get_llm(max_tokens=650, model=model),
        max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
        max_iter=AGENT_MAX_ITER,
        verbose=False,
    )
    task = Task(
        description=load_prompt(
            "assumption_task",
            idea=idea,
            target_customer=target_customer or "not specified",
            problem=problem or "not specified",
            context=context,
        ),
        expected_output=load_prompt("assumption_output"),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_assumptions(
    idea: str,
    target_customer: str,
    problem: str,
    swot: dict | None,
    market_opportunity: dict | None,
    mvp: dict | None,
    results: list,
    allow_local: bool = False,
) -> dict:
    sources = compact_sources(results)
    valid_ids = {source["sourceId"] for source in sources}
    context = compact_json(
        {
            "swot": swot,
            "segments": (market_opportunity or {}).get("segments", [])[:3],
            "features": (mvp or {}).get("features", [])[:3],
            "sources": sources,
        },
        max_chars=3000,
    )
    try:
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, target_customer, problem, context, model),
            primary=primary_for("assumptions"),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("Assumption agent returned no valid JSON")
            raise ValueError("Assumption analysis did not return a valid result.")
        data["assumptions"] = [
            {
                **item,
                "riskIfWrong": (item.get("riskIfWrong") or "").strip() or None,
                "timeToValidate": (item.get("timeToValidate") or "").strip() or None,
                "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids),
            }
            for item in _usable_assumptions(data)[:_MAX_ASSUMPTIONS]
        ]
        return data
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "Assumption agent: LLM unavailable, using deterministic assumptions",
            exc_info=True,
        )
        return deterministic_assumptions(idea, target_customer, problem, swot, market_opportunity, mvp)
