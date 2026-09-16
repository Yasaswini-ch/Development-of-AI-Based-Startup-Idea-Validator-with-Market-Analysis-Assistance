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


def _valid_string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _valid_shape(value: dict) -> bool:
    if not all(_valid_string_list(value.get(key)) for key in ("strengths", "weaknesses", "opportunities", "threats")):
        return False
    risks = value.get("risks")
    if not isinstance(risks, list):
        return False
    return all(
        isinstance(item, dict)
        and isinstance(item.get("risk"), str)
        and item.get("severity") in _LEVELS
        and item.get("likelihood") in _LEVELS
        for item in risks
    )


def _build_crew(idea: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="SWOT and Risk Analyst",
        goal="Produce concise, evidence-grounded strategic strengths, weaknesses, opportunities, threats, and risks.",
        backstory="A skeptical startup analyst who separates evidence from assumptions and never invents unsupported facts.",
        # Rebalanced to 750 (was 900, briefly tried 250 then 550) - see
        # market_agent.py for the full rationale; SWOT's schema (4 list
        # fields plus per-risk severity/likelihood) is similarly verbose
        # and was confirmed live to truncate at 550.
        llm=get_llm(max_tokens=750, model=model),
        verbose=False,
    )
    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Validated pipeline context: {context}\n\n"
            "Use only this context. Return up to four concise items in each SWOT category and up to four risks. "
            "Rate severity and likelihood as low, medium, high, or unknown. Use unknown when evidence is insufficient."
        ),
        expected_output=(
            'One JSON object only: {"strengths":["..."],"weaknesses":["..."],'
            '"opportunities":["..."],"threats":["..."],"risks":['
            '{"risk":"...","severity":"low|medium|high|unknown",'
            '"likelihood":"low|medium|high|unknown"}]}.'
        ),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_swot(
    idea: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    white_space: dict | None,
    results: list,
) -> dict:
    context = compact_json(
        {
            "marketOpportunity": market_opportunity,
            "competitors": competitors,
            "whiteSpace": white_space,
            "sources": compact_sources(results),
        }
    )
    try:
        output = kickoff_with_fallback(lambda model: _build_crew(idea, context, model))
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("SWOT agent returned no valid JSON")
            raise ValueError("SWOT analysis did not return a valid result.")

        for key in ("strengths", "weaknesses", "opportunities", "threats"):
            data[key] = data[key][:_MAX_ITEMS]
        data["risks"] = data["risks"][:_MAX_RISKS]
        return data
    except Exception:
        logger.warning(
            "SWOT: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_swot(idea, market_opportunity, competitors, white_space, results)
