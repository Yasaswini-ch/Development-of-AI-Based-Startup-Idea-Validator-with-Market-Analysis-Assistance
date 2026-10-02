"""Go-to-market strategy grounded in validated market artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_gtm
from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback, primary_for, AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER
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
_FIT_SCORES = {"high", "medium", "low"}


def _valid_channel_list(value) -> bool:
    """Each channel is {"text": str, "sourceIds": [str]} with optional
    "tactics": [str] and "fitScore": "high"|"medium"|"low".
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
        tactics = item.get("tactics")
        if tactics is not None and not (isinstance(tactics, list) and all(isinstance(t, str) for t in tactics)):
            return False
        fit = item.get("fitScore")
        if fit is not None and fit not in _FIT_SCORES:
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
        # Bumped to 600 (was 450) to accommodate per-channel tactics[] array
        # added in the GTM prompt update. 450 is the confirmed safe floor for
        # JSON completeness; 600 leaves headroom for 2-3 tactics per channel
        # without risk of truncation.
        llm=get_llm(max_tokens=600, model=model),
        max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
        max_iter=AGENT_MAX_ITER,
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
            # A different primary from mvp_agent's default (qwen3.8-27b) on
            # purpose: graph.py fans GTM and MVP out to run concurrently
            # (they have no dependency on each other), so both hitting the
            # same Groq model at the same instant was a guaranteed
            # same-bucket collision on every single request, not just
            # under team load - confirmed live, this was the one
            # contention point that didn't need concurrent *traffic* to
            # trigger, only a single validation run.
            primary=primary_for("gtm"),
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
            {
                "text": item["text"].strip(),
                "tactics": [t.strip() for t in (item.get("tactics") or [])[:3] if isinstance(t, str) and t.strip()],
                "fitScore": item.get("fitScore") if item.get("fitScore") in _FIT_SCORES else None,
                "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids),
            }
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
