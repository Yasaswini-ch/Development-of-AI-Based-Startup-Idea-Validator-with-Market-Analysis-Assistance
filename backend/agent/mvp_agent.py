"""MVP feature recommendations grounded in SWOT and customer evidence."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_mvp
from .llm import get_llm, kickoff_with_fallback
from .structured_output import compact_json, compact_sources, extract_json_object

logger = logging.getLogger(__name__)

_LEVELS = {"low", "medium", "high", "unknown"}
_MAX_FEATURES = 5


def _valid_source_ids(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


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
        and _valid_source_ids(item.get("sourceIds", []))
        for item in features
    )


def _sanitize_source_ids(value, valid_ids: set[str]) -> list[str]:
    """Drop any sourceId the model invented that isn't in the sources it
    was given - same rule swot_agent.py follows.
    """
    if not isinstance(value, list):
        return []
    seen = set()
    out = []
    for item in value:
        if isinstance(item, str) and item in valid_ids and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _build_crew(idea: str, problem: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="MVP Feature Recommendation Analyst",
        goal="Prioritize the smallest feature set that tests the startup's riskiest assumptions.",
        backstory="A product strategist who resists feature bloat and ties every recommendation to validated customer evidence.",
        # Rebalanced to 450 (was 800, briefly tried 250) - see
        # market_agent.py for the full rationale; 250 was confirmed live to
        # truncate JSON output itself, not just hit the rate limit.
        llm=get_llm(max_tokens=450, model=model),
        verbose=False,
    )
    task = Task(
        description=(
            f'Startup idea: "{idea}"\nProblem: {problem or "not specified"}\n'
            f"SWOT and customer context: {context}\n\n"
            "The context's \"sources\" array lists sourceId values (e.g. \"src-1\"). "
            "Recommend at most five ordered MVP features. Keep each feature testable and narrow. "
            "Rate impact and effort as low, medium, high, or unknown. Every feature needs a "
            "\"sourceIds\" array citing the sourceId(s) of the source(s) that support it - use an "
            "empty array only when a feature isn't tied to a specific source, never invent a "
            "sourceId that isn't in the context's sources list."
        ),
        expected_output=(
            'One JSON object only: {"features":[{"feature":"...","rationale":"...",'
            '"impact":"low|medium|high|unknown","effort":"low|medium|high|unknown",'
            '"sourceIds":["src-1"]}]}.'
        ),
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
            {**item, "sourceIds": _sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["features"][:_MAX_FEATURES]
        ]
        return data
    except Exception:
        logger.warning(
            "MVP: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_mvp(idea, problem, swot, market_opportunity)
