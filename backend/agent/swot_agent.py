"""SWOT and risk analysis grounded in existing pipeline artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_swot
from .llm import get_llm, kickoff_with_fallback
from .structured_output import compact_json, compact_sources, extract_json_object

logger = logging.getLogger(__name__)

_LEVELS = {"low", "medium", "high", "unknown"}
_MAX_ITEMS = 4
_MAX_RISKS = 4

_SWOT_KEYS = ("strengths", "weaknesses", "opportunities", "threats")


def _valid_source_ids(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


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
        if not _valid_source_ids(item.get("sourceIds", [])):
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
        and _valid_source_ids(item.get("sourceIds", []))
        for item in risks
    )


def _build_crew(idea: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="SWOT and Risk Analyst",
        goal="Produce concise, evidence-grounded strategic strengths, weaknesses, opportunities, threats, and risks.",
        backstory="A skeptical startup analyst who separates evidence from assumptions and never invents unsupported facts.",
        # Rebalanced to 750 (was 900, briefly tried 250 then 550) - see
        # market_agent.py for the full rationale; SWOT's schema (4 list
        # fields plus per-item sourceIds plus per-risk severity/likelihood)
        # is similarly verbose and was confirmed live to truncate at 550.
        llm=get_llm(max_tokens=750, model=model),
        verbose=False,
    )
    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Validated pipeline context: {context}\n\n"
            "The context's \"sources\" array lists sourceId values (e.g. \"src-1\"). "
            "Use only this context. Return up to four concise items in each SWOT category and up to four risks. "
            "Every item and risk needs a \"sourceIds\" array citing the sourceId(s) of the source(s) it's grounded "
            "in - use an empty array only when a claim is a structural observation not tied to a specific source, "
            "never invent a sourceId that isn't in the context's sources list. "
            "Rate severity and likelihood as low, medium, high, or unknown. Use unknown when evidence is insufficient."
        ),
        expected_output=(
            'One JSON object only: {"strengths":[{"text":"...","sourceIds":["src-1"]}],'
            '"weaknesses":[{"text":"...","sourceIds":[]}],'
            '"opportunities":[{"text":"...","sourceIds":["src-2"]}],'
            '"threats":[{"text":"...","sourceIds":["src-3"]}],"risks":['
            '{"risk":"...","severity":"low|medium|high|unknown",'
            '"likelihood":"low|medium|high|unknown","sourceIds":["src-1"]}]}.'
        ),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def _sanitize_source_ids(value, valid_ids: set[str]) -> list[str]:
    """Drop any sourceId the model invented that isn't actually in the
    sources it was given - never let a hallucinated citation reach the UI,
    same honesty-first rule the rest of this pipeline follows.
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


def _sanitize_claims(items: list, valid_ids: set[str], limit: int) -> list[dict]:
    return [
        {"text": item["text"].strip(), "sourceIds": _sanitize_source_ids(item.get("sourceIds"), valid_ids)}
        for item in items[:limit]
    ]


def analyze_swot(
    idea: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    white_space: dict | None,
    results: list,
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
        output = kickoff_with_fallback(lambda model: _build_crew(idea, context, model))
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("SWOT agent returned no valid JSON")
            raise ValueError("SWOT analysis did not return a valid result.")

        for key in _SWOT_KEYS:
            data[key] = _sanitize_claims(data[key], valid_ids, _MAX_ITEMS)
        data["risks"] = [
            {**risk, "sourceIds": _sanitize_source_ids(risk.get("sourceIds"), valid_ids)}
            for risk in data["risks"][:_MAX_RISKS]
        ]
        return data
    except Exception:
        logger.warning(
            "SWOT: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_swot(idea, market_opportunity, competitors, white_space, results)
