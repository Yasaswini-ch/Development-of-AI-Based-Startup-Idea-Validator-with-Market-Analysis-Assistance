"""MVP feature recommendations grounded in SWOT and customer evidence."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_mvp
from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback, primary_for, AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER
from .verification import audit, strip_unsupported, verify_claims
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
_MAX_FEATURES = 4
_MAX_EXTRA = 2


def _valid_extra_list(value) -> bool:
    """niceToHave/deferred items: {feature: str, rationale: str, sourceIds: [...]}"""
    if not isinstance(value, list):
        return False
    return all(
        isinstance(item, dict)
        and isinstance(item.get("feature"), str)
        and isinstance(item.get("rationale"), str)
        and valid_source_ids(item.get("sourceIds", []))
        for item in value
    )


def _valid_shape(value: dict) -> bool:
    features = value.get("features")
    if not isinstance(features, list) or not features:
        return False
    if not all(
        isinstance(item, dict)
        and isinstance(item.get("feature"), str)
        and isinstance(item.get("rationale"), str)
        and item.get("impact") in _LEVELS
        and item.get("effort") in _LEVELS
        and valid_source_ids(item.get("sourceIds", []))
        for item in features
    ):
        return False
    # niceToHave and deferred are optional
    for key in ("niceToHave", "deferred"):
        extra = value.get(key)
        if extra is not None and not _valid_extra_list(extra):
            return False
    return True


def _build_crew(idea: str, problem: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="MVP Feature Recommendation Analyst",
        goal="Prioritize the smallest feature set that tests the startup's riskiest assumptions.",
        backstory=load_prompt("mvp_system"),
        # Bumped to 600 (was 450) to accommodate niceToHave[] and deferred[]
        # arrays added to the MVP prompt. 450 was the confirmed safe floor for
        # JSON completeness; 600 leaves headroom for the extra feature lists.
        llm=get_llm(max_tokens=600, model=model),
        max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
        max_iter=AGENT_MAX_ITER,
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
    allow_local: bool = False,
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
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, problem, context, model),
            primary=primary_for("mvp"),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("MVP agent returned no valid JSON")
            raise ValueError("MVP analysis did not return a valid result.")
        data["features"] = [
            {**item, "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["features"][:_MAX_FEATURES]
        ]
        for key in ("niceToHave", "deferred"):
            extra = data.get(key) or []
            data[key] = [
                {**item, "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
                for item in extra[:_MAX_EXTRA]
            ]

        # Grounding verification (see verification.py) - the rationale is
        # the actual evidence-backed claim per feature; the feature name
        # itself is just a label, nothing to fact-check.
        snippets = {s["sourceId"]: s["snippet"] for s in sources}
        flat = [{"text": item["rationale"], "sourceIds": item["sourceIds"]} for item in data["features"]]
        supported = verify_claims(idea, flat, snippets, allow_local=allow_local)
        verified = strip_unsupported(flat, supported)
        data["verification"] = audit(flat, supported)
        for item, result in zip(data["features"], verified):
            item["sourceIds"] = result["sourceIds"]

        return data
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "MVP: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_mvp(idea, problem, swot, market_opportunity)
