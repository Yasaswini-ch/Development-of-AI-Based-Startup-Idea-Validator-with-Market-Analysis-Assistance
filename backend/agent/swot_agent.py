"""SWOT and risk analysis grounded in existing pipeline artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_swot
from .llm import get_llm, kickoff_with_fallback
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

_SWOT_KEYS = (
    "strengths",
    "weaknesses",
    "opportunities",
    "threats",
)


def _valid_claim_list(value) -> bool:
    """
    Validate a SWOT claim list.

    Each item must have:

        {
            "text": "...",
            "sourceIds": ["src-1"]
        }

    sourceIds can be empty when the claim is a structural
    observation that is not tied to a specific source.
    """

    if not isinstance(value, list):
        return False

    for item in value:
        if not isinstance(item, dict):
            return False

        if not isinstance(item.get("text"), str):
            return False

        if not item["text"].strip():
            return False

        if not valid_source_ids(
            item.get("sourceIds", [])
        ):
            return False

    return True


def _valid_shape(value: dict) -> bool:
    """
    Validate the complete SWOT response structure.
    """

    # ---------------------------------------------------------
    # Validate SWOT categories
    # ---------------------------------------------------------

    if not all(
        _valid_claim_list(value.get(key))
        for key in _SWOT_KEYS
    ):
        return False

    # ---------------------------------------------------------
    # Validate risks
    # ---------------------------------------------------------

    risks = value.get("risks")

    if not isinstance(risks, list):
        return False

    for item in risks:
        if not isinstance(item, dict):
            return False

        if not isinstance(item.get("risk"), str):
            return False

        if not item["risk"].strip():
            return False

        if item.get("severity") not in _LEVELS:
            return False

        if item.get("likelihood") not in _LEVELS:
            return False

        if not valid_source_ids(
            item.get("sourceIds", [])
        ):
            return False

    return True


def _build_crew(
    idea: str,
    context: str,
    model: str,
) -> Crew:
    """
    Build the CrewAI SWOT analysis crew.
    """

    analyst = Agent(
        role="SWOT and Risk Analyst",

        goal=(
            "Produce concise, evidence-grounded strategic "
            "strengths, weaknesses, opportunities, threats, "
            "and risks."
        ),

        backstory=(
            "A skeptical startup analyst who separates "
            "evidence from assumptions and never invents "
            "unsupported facts."
        ),

        llm=get_llm(
            max_tokens=750,
            model=model,
        ),

        verbose=False,
    )

    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Validated pipeline context: {context}\n\n"

            "The context's \"sources\" array lists sourceId "
            'values (e.g. "src-1"). '

            "Use only the provided context. "

            "Return up to four concise items in each SWOT "
            "category and up to four risks. "

            "Every SWOT item and every risk must contain a "
            "\"sourceIds\" array citing the sourceId(s) of "
            "the source(s) it is grounded in. "

            "Use an empty sourceIds array only when the claim "
            "is a structural observation that is not tied to "
            "a specific source. "

            "Never invent a sourceId that is not present in "
            "the context's sources list. "

            "Rate severity and likelihood as low, medium, "
            "high, or unknown. "

            "Use unknown whenever the available evidence "
            "is insufficient."
        ),

        expected_output=(
            'One JSON object only: '

            '{"strengths":['
            '{"text":"...","sourceIds":["src-1"]}'
            '],'

            '"weaknesses":['
            '{"text":"...","sourceIds":[]}'
            '],'

            '"opportunities":['
            '{"text":"...","sourceIds":["src-2"]}'
            '],'

            '"threats":['
            '{"text":"...","sourceIds":["src-3"]}'
            '],'

            '"risks":['
            '{"risk":"...",'
            '"severity":"low|medium|high|unknown",'
            '"likelihood":"low|medium|high|unknown",'
            '"sourceIds":["src-1"]}'
            ']}'
        ),

        agent=analyst,
    )

    return Crew(
        agents=[analyst],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )


def _sanitize_claims(
    items: list,
    valid_ids: set[str],
    limit: int,
) -> list[dict]:
    """
    Clean and sanitize source IDs for SWOT claims.
    """

    sanitized = []

    for item in items[:limit]:
        sanitized.append(
            {
                "text": item["text"].strip(),
                "sourceIds": sanitize_source_ids(
                    item.get("sourceIds"),
                    valid_ids,
                ),
            }
        )

    return sanitized


def analyze_swot(
    idea: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    white_space: dict | None,
    results: list,
) -> dict:
    """
    Analyze startup strengths, weaknesses,
    opportunities, threats, and risks.

    Source IDs are taken from validated pipeline results
    and sanitized before returning the final response.
    """

    # ---------------------------------------------------------
    # Prepare sources
    # ---------------------------------------------------------

    sources = compact_sources(results)

    valid_ids = {
        source["sourceId"]
        for source in sources
    }

    # ---------------------------------------------------------
    # Prepare LLM context
    # ---------------------------------------------------------

    context = compact_json(
        {
            "marketOpportunity": market_opportunity,
            "competitors": competitors,
            "whiteSpace": white_space,
            "sources": sources,
        }
    )

    try:
        # -----------------------------------------------------
        # Run CrewAI
        # -----------------------------------------------------

        output = kickoff_with_fallback(
            lambda model: _build_crew(
                idea,
                context,
                model,
            )
        )

        # -----------------------------------------------------
        # Extract JSON
        # -----------------------------------------------------

        data = extract_json_object(
            output.raw,
            _valid_shape,
        )

        if data is None:
            logger.warning(
                "SWOT agent returned no valid JSON"
            )

            raise ValueError(
                "SWOT analysis did not return a valid result."
            )

        # -----------------------------------------------------
        # Sanitize SWOT claims
        # -----------------------------------------------------

        for key in _SWOT_KEYS:
            data[key] = _sanitize_claims(
                data[key],
                valid_ids,
                _MAX_ITEMS,
            )

        # -----------------------------------------------------
        # Sanitize risks
        # -----------------------------------------------------

        data["risks"] = [
            {
                "risk": risk["risk"].strip(),
                "severity": risk["severity"],
                "likelihood": risk["likelihood"],
                "sourceIds": sanitize_source_ids(
                    risk.get("sourceIds"),
                    valid_ids,
                ),
            }
            for risk in data["risks"][:_MAX_RISKS]
        ]

        return data

    except Exception:
        # -----------------------------------------------------
        # Deterministic fallback
        #
        # results is passed so the fallback can preserve
        # source attribution.
        # -----------------------------------------------------

        logger.warning(
            "SWOT: LLM analysis unavailable, "
            "using deterministic evidence-based fallback",
            exc_info=True,
        )

        return deterministic_swot(
            idea,
            market_opportunity,
            competitors,
            white_space,
            results,
        )