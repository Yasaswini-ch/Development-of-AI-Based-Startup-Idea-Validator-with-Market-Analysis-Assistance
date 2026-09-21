"""MVP feature recommendations grounded in SWOT and customer evidence."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_mvp
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
_MAX_FEATURES = 5


def _valid_shape(value: dict) -> bool:
    """
    Validate the complete MVP response structure.

    Expected structure:

    {
        "features": [
            {
                "feature": "...",
                "rationale": "...",
                "impact": "low|medium|high|unknown",
                "effort": "low|medium|high|unknown",
                "sourceIds": ["src-1"]
            }
        ]
    }
    """

    features = value.get("features")

    if not isinstance(features, list) or not features:
        return False

    for item in features:
        if not isinstance(item, dict):
            return False

        if not isinstance(item.get("feature"), str):
            return False

        if not item["feature"].strip():
            return False

        if not isinstance(item.get("rationale"), str):
            return False

        if not item["rationale"].strip():
            return False

        if item.get("impact") not in _LEVELS:
            return False

        if item.get("effort") not in _LEVELS:
            return False

        if not valid_source_ids(
            item.get("sourceIds", [])
        ):
            return False

    return True


def _build_crew(
    idea: str,
    problem: str,
    context: str,
    model: str,
) -> Crew:
    """
    Build the CrewAI MVP recommendation crew.
    """

    analyst = Agent(
        role="MVP Feature Recommendation Analyst",

        goal=(
            "Prioritize the smallest feature set that tests "
            "the startup's riskiest assumptions."
        ),

        backstory=(
            "A product strategist who resists feature bloat "
            "and ties every recommendation to validated "
            "customer evidence."
        ),

        llm=get_llm(
            max_tokens=450,
            model=model,
        ),

        verbose=False,
    )

    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f'Problem: {problem or "not specified"}\n'
            f"SWOT and customer context: {context}\n\n"

            "The context's \"sources\" array lists sourceId "
            'values (e.g. "src-1"). '

            "Recommend at most five ordered MVP features. "

            "Keep every feature testable, narrow, and practical. "

            "Rate impact and effort as one of: "
            "low, medium, high, or unknown. "

            "Every feature must contain a \"sourceIds\" array "
            "citing the sourceId(s) of the source(s) that "
            "support that feature. "

            "Use an empty sourceIds array only when the feature "
            "is not tied to a specific source. "

            "Never invent a sourceId that is not present in "
            "the context's sources list. "

            "Do not invent customer traction, partnerships, "
            "revenue, market validation, or other unsupported facts."
        ),

        expected_output=(
            'One JSON object only: '
            '{"features":['
            '{"feature":"...",'
            '"rationale":"...",'
            '"impact":"low|medium|high|unknown",'
            '"effort":"low|medium|high|unknown",'
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


def analyze_mvp(
    idea: str,
    problem: str,
    swot: dict | None,
    market_opportunity: dict | None,
    results: list,
) -> dict:
    """
    Analyze and prioritize MVP features.

    Source IDs are collected from the validated pipeline
    results and attached to evidence-grounded features.
    """

    # ---------------------------------------------------------
    # Prepare validated source information
    # ---------------------------------------------------------

    sources = compact_sources(results)

    valid_ids = {
        source["sourceId"]
        for source in sources
    }

    # ---------------------------------------------------------
    # Prepare compact context for the LLM
    # ---------------------------------------------------------

    context = compact_json(
        {
            "swot": swot,

            "segments": (
                market_opportunity or {}
            ).get(
                "segments",
                [],
            )[:4],

            "sources": sources,
        },
        max_chars=3500,
    )

    try:
        # -----------------------------------------------------
        # Run CrewAI analysis with model fallback
        # -----------------------------------------------------

        output = kickoff_with_fallback(
            lambda model: _build_crew(
                idea,
                problem,
                context,
                model,
            )
        )

        # -----------------------------------------------------
        # Extract and validate JSON
        # -----------------------------------------------------

        data = extract_json_object(
            output.raw,
            _valid_shape,
        )

        if data is None:
            logger.warning(
                "MVP agent returned no valid JSON"
            )

            raise ValueError(
                "MVP analysis did not return a valid result."
            )

        # -----------------------------------------------------
        # Sanitize source IDs
        # -----------------------------------------------------

        data["features"] = [
            {
                "feature": item["feature"].strip(),
                "rationale": item["rationale"].strip(),
                "impact": item["impact"],
                "effort": item["effort"],
                "sourceIds": sanitize_source_ids(
                    item.get("sourceIds"),
                    valid_ids,
                ),
            }
            for item in data["features"][:_MAX_FEATURES]
        ]

        return data

    except Exception:
        # -----------------------------------------------------
        # Deterministic fallback
        #
        # IMPORTANT:
        # results is passed so deterministic_mvp() can preserve
        # source attribution just like deterministic_swot().
        # -----------------------------------------------------

        logger.warning(
            "MVP: LLM analysis unavailable, "
            "using deterministic evidence-based fallback",
            exc_info=True,
        )

        return deterministic_mvp(
            idea,
            problem,
            swot,
            market_opportunity,
            results,
        )