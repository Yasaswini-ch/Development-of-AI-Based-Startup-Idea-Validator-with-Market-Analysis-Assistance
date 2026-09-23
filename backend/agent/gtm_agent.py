"""Go-to-market strategy grounded in validated market artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_gtm
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

_MAX_CHANNELS = 4


def _valid_channel_list(value) -> bool:
    """Each channel is {"text": str, "sourceIds": [str]}, same claim shape
    swot_agent.py uses, so a recommended channel can cite the source(s) it's
    grounded in.
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
    return (
        isinstance(value.get("positioning"), str)
        and valid_source_ids(value.get("positioningSourceIds", []))
        and _valid_channel_list(value.get("channels"))
        and isinstance(value.get("earlyCustomerApproach"), str)
        and valid_source_ids(value.get("earlyCustomerApproachSourceIds", []))
    )


def _build_crew(idea: str, target_customer: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="Go-to-Market Strategy Analyst",
        goal="Create a focused positioning and early acquisition plan grounded in validated customer and competitor evidence.",
        backstory=load_prompt("gtm_system"),
        # Rebalanced to 450 (was 800, briefly tried 250) - see
        # market_agent.py for the full rationale; 250 was confirmed live to
        # truncate JSON output itself, not just hit the rate limit.
        llm=get_llm(max_tokens=450, model=model),
        verbose=False,
    )
    task = Task(
        description=load_prompt(
            "gtm_task", idea=idea, target_customer=target_customer or "not specified", context=context
        ),
        expected_output=load_prompt("gtm_output"),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_gtm(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    swot: dict | None,
    results: list,
    allow_local: bool = False,
) -> dict:
    sources = compact_sources(results)
    valid_ids = {source["sourceId"] for source in sources}
    context = compact_json(
        {
            "marketOpportunity": market_opportunity,
            "competitors": competitors,
            "swot": swot,
            "sources": sources,
        },
        max_chars=4000,
    )
    try:
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, target_customer, context, model),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("GTM agent returned no valid JSON")
            raise ValueError("GTM analysis did not return a valid result.")
        data["positioningSourceIds"] = sanitize_source_ids(data.get("positioningSourceIds"), valid_ids)
        data["earlyCustomerApproachSourceIds"] = sanitize_source_ids(
            data.get("earlyCustomerApproachSourceIds"), valid_ids
        )
        data["channels"] = [
            {"text": item["text"].strip(), "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["channels"][:_MAX_CHANNELS]
        ]

        # Grounding verification (see verification.py).
        snippets = {s["sourceId"]: s["snippet"] for s in sources}
        flat = (
            [{"text": data["positioning"], "sourceIds": data["positioningSourceIds"]}]
            + [{"text": data["earlyCustomerApproach"], "sourceIds": data["earlyCustomerApproachSourceIds"]}]
            + data["channels"]
        )
        supported = verify_claims(idea, flat, snippets, allow_local=allow_local)
        verified = strip_unsupported(flat, supported)
        data["positioningSourceIds"] = verified[0]["sourceIds"]
        data["earlyCustomerApproachSourceIds"] = verified[1]["sourceIds"]
        for channel, result in zip(data["channels"], verified[2:]):
            channel["sourceIds"] = result["sourceIds"]

        return data
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "GTM: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_gtm(idea, target_customer, market_opportunity, competitors, swot)
