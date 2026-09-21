"""Go-to-market strategy grounded in validated market artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_gtm
from .llm import get_llm, kickoff_with_fallback
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
    """
    Validate the recommended acquisition channels.

    Each channel must have:
        {
            "text": str,
            "sourceIds": [str]
        }

    sourceIds may be empty when the recommendation is not tied
    to a specific source.
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
    """
    Validate the complete GTM response structure.
    """
    return (
        isinstance(value.get("positioning"), str)
        and bool(value["positioning"].strip())
        and valid_source_ids(value.get("positioningSourceIds", []))
        and _valid_channel_list(value.get("channels"))
        and isinstance(value.get("earlyCustomerApproach"), str)
        and bool(value["earlyCustomerApproach"].strip())
        and valid_source_ids(
            value.get("earlyCustomerApproachSourceIds", [])
        )
    )


def _build_crew(
    idea: str,
    target_customer: str,
    context: str,
    model: str,
) -> Crew:
    """
    Build the CrewAI GTM analysis crew.
    """

    analyst = Agent(
        role="Go-to-Market Strategy Analyst",
        goal=(
            "Create a focused positioning and early acquisition plan "
            "grounded in validated customer and competitor evidence."
        ),
        backstory=(
            "An early-stage growth strategist who recommends a few "
            "testable channels instead of generic marketing lists."
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
            f'Target customer: {target_customer or "not specified"}\n'
            f"Validated strategy context: {context}\n\n"

            "The context's \"sources\" array lists sourceId values "
            '(e.g. "src-1"). '

            "Write one differentiated positioning statement, "
            "up to four specific acquisition channels, and one "
            "practical early-customer approach. "

            "Do not invent traction or partnerships. "

            "Give the positioning statement a "
            '"positioningSourceIds" array, each channel a '
            '"sourceIds" array, and the early-customer approach an '
            '"earlyCustomerApproachSourceIds" array. '

            "Each sourceIds array must contain only sourceId values "
            "that actually exist in the context's sources list. "

            "Use an empty array only when the recommendation is not "
            "tied to a specific source. "
            "Never invent a sourceId."
        ),

        expected_output=(
            'One JSON object only: '
            '{"positioning":"...",'
            '"positioningSourceIds":["src-1"],'
            '"channels":['
            '{"text":"...","sourceIds":["src-2"]}'
            '],'
            '"earlyCustomerApproach":"...",'
            '"earlyCustomerApproachSourceIds":[]}'
        ),

        agent=analyst,
    )

    return Crew(
        agents=[analyst],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )


def analyze_gtm(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    swot: dict | None,
    results: list,
) -> dict:
    """
    Analyze the startup's go-to-market strategy.

    Source IDs are collected from the validated pipeline results
    and attached to every evidence-grounded recommendation.
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
            "marketOpportunity": market_opportunity,
            "competitors": competitors,
            "swot": swot,
            "sources": sources,
        },
        max_chars=4000,
    )

    try:
        # -----------------------------------------------------
        # Run CrewAI analysis with model fallback
        # -----------------------------------------------------

        output = kickoff_with_fallback(
            lambda model: _build_crew(
                idea,
                target_customer,
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
                "GTM agent returned no valid JSON"
            )

            raise ValueError(
                "GTM analysis did not return a valid result."
            )

        # -----------------------------------------------------
        # Sanitize positioning source IDs
        # -----------------------------------------------------

        data["positioningSourceIds"] = sanitize_source_ids(
            data.get("positioningSourceIds"),
            valid_ids,
        )

        # -----------------------------------------------------
        # Sanitize early customer approach source IDs
        # -----------------------------------------------------

        data["earlyCustomerApproachSourceIds"] = (
            sanitize_source_ids(
                data.get(
                    "earlyCustomerApproachSourceIds"
                ),
                valid_ids,
            )
        )

        # -----------------------------------------------------
        # Sanitize channel source IDs
        # -----------------------------------------------------

        data["channels"] = [
            {
                "text": item["text"].strip(),
                "sourceIds": sanitize_source_ids(
                    item.get("sourceIds"),
                    valid_ids,
                ),
            }
            for item in data["channels"][:_MAX_CHANNELS]
        ]

        return data

    except Exception:
        # -----------------------------------------------------
        # Deterministic fallback
        #
        # IMPORTANT:
        # results is passed here so the fallback can preserve
        # source attribution just like swot_agent.py.
        # -----------------------------------------------------

        logger.warning(
            "GTM: LLM analysis unavailable, "
            "using deterministic evidence-based fallback",
            exc_info=True,
        )

        return deterministic_gtm(
            idea,
            target_customer,
            market_opportunity,
            competitors,
            swot,
            results,
        )