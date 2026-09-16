"""Go-to-market strategy grounded in validated market artifacts."""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_gtm
from .llm import get_llm, kickoff_with_fallback
from .structured_output import compact_json, extract_json_object

logger = logging.getLogger(__name__)

_MAX_CHANNELS = 4


def _valid_shape(value: dict) -> bool:
    return (
        isinstance(value.get("positioning"), str)
        and isinstance(value.get("channels"), list)
        and all(isinstance(item, str) and item.strip() for item in value["channels"])
        and isinstance(value.get("earlyCustomerApproach"), str)
    )


def _build_crew(idea: str, target_customer: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="Go-to-Market Strategy Analyst",
        goal="Create a focused positioning and early acquisition plan grounded in validated customer and competitor evidence.",
        backstory="An early-stage growth strategist who recommends a few testable channels instead of generic marketing lists.",
        # Rebalanced to 450 (was 800, briefly tried 250) - see
        # market_agent.py for the full rationale; 250 was confirmed live to
        # truncate JSON output itself, not just hit the rate limit.
        llm=get_llm(max_tokens=450, model=model),
        verbose=False,
    )
    task = Task(
        description=(
            f'Startup idea: "{idea}"\nTarget customer: {target_customer or "not specified"}\n'
            f"Validated strategy context: {context}\n\n"
            "Write one differentiated positioning statement, up to four specific acquisition channels, "
            "and one practical early-customer approach. Do not invent traction or partnerships."
        ),
        expected_output=(
            'One JSON object only: {"positioning":"...","channels":["..."],'
            '"earlyCustomerApproach":"..."}.'
        ),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_gtm(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    swot: dict | None,
) -> dict:
    context = compact_json(
        {
            "marketOpportunity": market_opportunity,
            "competitors": competitors,
            "swot": swot,
        },
        max_chars=4000,
    )
    try:
        output = kickoff_with_fallback(lambda model: _build_crew(idea, target_customer, context, model))
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("GTM agent returned no valid JSON")
            raise ValueError("GTM analysis did not return a valid result.")
        data["channels"] = data["channels"][:_MAX_CHANNELS]
        return data
    except Exception:
        logger.warning(
            "GTM: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_gtm(idea, target_customer, market_opportunity, competitors, swot)
