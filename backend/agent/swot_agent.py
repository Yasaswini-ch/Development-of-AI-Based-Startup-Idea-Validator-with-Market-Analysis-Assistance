"""SWOT and risk analysis grounded in existing pipeline artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_swot
from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback
from .verification import strip_unsupported, verify_claims
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
_MAX_ITEMS = 4
_MAX_RISKS = 4

_SWOT_KEYS = ("strengths", "weaknesses", "opportunities", "threats")


def _valid_claim_list(value) -> bool:
    """Each SWOT item is {"text": str, "sourceIds": [str]} - not a bare
    string - so every claim can cite the source(s) it's grounded in (see
    docs/unique-features-plan.md §5.1/§3). sourceIds may be an empty list
    when a claim isn't tied to a specific source (e.g. a structural
    observation), but the field itself is always present.
    """
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict):
            return False
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            return False
        if not valid_source_ids(item.get("sourceIds", [])):
            return False
    return True


def _valid_shape(value: dict) -> bool:
    if not all(_valid_claim_list(value.get(key)) for key in _SWOT_KEYS):
        return False
    risks = value.get("risks")
    if not isinstance(risks, list):
        return False
    return all(
        isinstance(item, dict)
        and isinstance(item.get("risk"), str)
        and item.get("severity") in _LEVELS
        and item.get("likelihood") in _LEVELS
        and valid_source_ids(item.get("sourceIds", []))
        for item in risks
    )


def _build_crew(idea: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="SWOT and Risk Analyst",
        goal="Produce concise, evidence-grounded strategic strengths, weaknesses, opportunities, threats, and risks.",
        backstory=load_prompt("swot_system"),
        # Rebalanced to 750 (was 900, briefly tried 250 then 550) - see
        # market_agent.py for the full rationale; SWOT's schema (4 list
        # fields plus per-item sourceIds plus per-risk severity/likelihood)
        # is similarly verbose and was confirmed live to truncate at 550.
        llm=get_llm(max_tokens=750, model=model),
        verbose=False,
    )
    task = Task(
        description=load_prompt("swot_task", idea=idea, context=context),
        expected_output=load_prompt("swot_output"),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def _sanitize_claims(items: list, valid_ids: set[str], limit: int) -> list[dict]:
    return [
        {"text": item["text"].strip(), "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
        for item in items[:limit]
    ]


def analyze_swot(
    idea: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    white_space: dict | None,
    results: list,
    allow_local: bool = False,
) -> dict:
    sources = compact_sources(results)
    valid_ids = {source["sourceId"] for source in sources}
    context = compact_json(
        {
            "marketOpportunity": market_opportunity,
            "competitors": competitors,
            "whiteSpace": white_space,
            "sources": sources,
        }
    )
    try:
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, context, model),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("SWOT agent returned no valid JSON")
            raise ValueError("SWOT analysis did not return a valid result.")

        for key in _SWOT_KEYS:
            data[key] = _sanitize_claims(data[key], valid_ids, _MAX_ITEMS)
        data["risks"] = [
            {**risk, "sourceIds": sanitize_source_ids(risk.get("sourceIds"), valid_ids)}
            for risk in data["risks"][:_MAX_RISKS]
        ]

        # Grounding verification (see verification.py) - confirms each
        # cited source actually supports the claim, not just that the
        # sourceId exists.
        snippets = {s["sourceId"]: s["snippet"] for s in sources}
        flat = (
            [item for key in _SWOT_KEYS for item in data[key]]
            + [{"text": risk["risk"], "sourceIds": risk["sourceIds"]} for risk in data["risks"]]
        )
        supported = verify_claims(idea, flat, snippets, allow_local=allow_local)
        verified = strip_unsupported(flat, supported)
        cursor = 0
        for key in _SWOT_KEYS:
            for item in data[key]:
                item["sourceIds"] = verified[cursor]["sourceIds"]
                cursor += 1
        for risk in data["risks"]:
            risk["sourceIds"] = verified[cursor]["sourceIds"]
            cursor += 1

        return data
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "SWOT: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_swot(idea, market_opportunity, competitors, white_space, results)
