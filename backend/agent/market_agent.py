"""
Market Opportunity & Customer Segmentation Analysis Agent (Milestone 2).

Takes the Web Search Agent's results and reasons about market size/growth
and customer segments - grounded in that real data, not invented. This is
the second stage of the pipeline: web_search runs first, and its results
are passed in here (context passing between agents).

Per the Milestone 2 guide, each segment needs its pain points, motivations,
and buying behavior - not just a segment name - so downstream consumers
(and founders reading the output) get something actionable, not a label.

Like the Web Search Agent, this deliberately avoids CrewAI's
output_pydantic/function-calling conversion for structured output - that
proved unreliable with our tested Groq model (repeated "tool_use_failed"
errors, then silent fallback to garbage text). Instead the task asks for
plain JSON in its answer, which we parse and validate ourselves, with a
safe fallback if parsing fails or no valid JSON can be found at all.
"""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_market_opportunity
from .llm import get_llm, kickoff_with_fallback
from .structured_output import extract_json_object

logger = logging.getLogger(__name__)

_MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 300
_MAX_SEGMENTS = 4
_MAX_TRENDS = 4


def _build_context(results: list) -> str:
    """Condense the real search results into a compact block of grounding
    text for the prompt - capped so we don't blow up the context window
    with everything retrieval.py fetched.

    Same fix as competitor_agent.py's _build_context, confirmed by the same
    live failure: a plain top-N-by-score slice can crowd out every "Market
    size & trends" result if their relevance score (word-overlap with the
    query) happens to be lower than results from other angles. Guarantee
    market-size results first claim on the context window; fill remaining
    slots with the next-best results from any angle for general grounding.
    """
    market_results = [r for r in results if r.get("angle") == "Market size & trends"]
    other_results = [r for r in results if r.get("angle") != "Market size & trends"]
    ordered = market_results + other_results

    lines = []
    for r in ordered[:_MAX_SOURCES_IN_CONTEXT]:
        snippet = (r.get("snippet") or "")[:_MAX_SNIPPET_LEN]
        lines.append(f"- {r.get('title', '')}: {snippet}")
    return "\n".join(lines) if lines else "No search results were available."


def _build_market_crew(idea: str, target_customer: str, problem: str, context: str, model: str) -> Crew:
    analyst = Agent(
        role="Market Opportunity & Customer Segmentation Analyst",
        goal=(
            "Turn raw search results into a structured market analysis: size, "
            "growth, and customer segments with their pain points, "
            "motivations, and buying behavior"
        ),
        backstory=(
            "A market analyst who only reasons from the evidence provided, "
            "never inventing statistics or segments that aren't supported by "
            "the given sources. Writes for a founder who needs to act on this, "
            "not a report that just restates what a segment is called."
        ),
        # Rebalanced to 750 (was 900, briefly tried 250 then 550). Market's
        # JSON schema (marketSize sentence + trends array + multi-field
        # segments) is the most verbose of the four agents and was
        # confirmed live to truncate into invalid JSON at 550, so it keeps
        # more headroom than mvp/gtm below even though all four still
        # collectively exceed Groq's ~1000 output-tokens/minute cap on the
        # primary model - the model-fallback chain (see llm.py) is the
        # actual safety net for whichever call(s) exceed the shared budget.
        llm=get_llm(max_tokens=750, model=model),
        verbose=False,
    )

    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Target customer: {target_customer or 'not specified'}\n"
            f"Problem being solved: {problem or 'not specified'}\n\n"
            "Here are real, current web search results about this idea's market:\n"
            f"{context}\n\n"
            "Based only on the information above, analyze:\n"
            "1. Market size (state whether the figures are global, regional, or "
            "niche if the sources indicate this) and growth trend. Include TAM, "
            "SAM, or CAGR only when the provided sources explicitly support those "
            "figures; otherwise state that they are not clear from the sources.\n"
            "2. Up to 4 notable trends or adoption patterns.\n"
            "3. Up to 4 customer segments - for each, their pain points (what "
            "problem they're trying to solve), motivations (what they care "
            "about / why they'd buy), and buying behavior (how they decide or "
            "purchase, if the sources suggest anything about this).\n"
            "Do not invent statistics, segments, or behaviors that aren't "
            "supported by the sources - if buying behavior isn't evident from "
            "the sources, say so plainly rather than guessing.\n"
            "Output strict JSON only: within JSON strings, never escape an "
            "apostrophe with a backslash - write don't directly, not don\\'t."
        ),
        expected_output=(
            "A single JSON object, and nothing else - no markdown code fences, no "
            "explanation before or after it, no placeholder text. Fill in real "
            "content from the sources above. For example, for a different idea "
            "this might look like:\n"
            '{"marketSize": "The global market was valued at $2.1 billion in 2024 '
            'and is growing at 12% annually; TAM/SAM are not clear from the provided sources.", '
            '"trends": ["Rising demand for subscription-based delivery", '
            '"Increased focus on eco-friendly packaging"], '
            '"segments": ['
            '{"segment": "Urban millennials", '
            '"painPoints": "Limited time to research and compare options", '
            '"motivations": "Convenience and sustainability credentials", '
            '"buyingBehavior": "Research online, prefer subscription models over one-off purchases"}, '
            '{"segment": "Budget-conscious families", '
            '"painPoints": "Existing options are too expensive for regular use", '
            '"motivations": "Value for money without sacrificing quality", '
            '"buyingBehavior": "Not clear from the sources"}'
            "]}\n"
            "Use at most 4 items in trends and 4 objects in segments, grounded "
            "only in the sources given to you."
        ),
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def _is_valid_segment(item) -> bool:
    if not isinstance(item, dict):
        return False
    required = ("segment", "painPoints", "motivations", "buyingBehavior")
    return all(isinstance(item.get(key), str) for key in required)


def _is_valid_shape(data: dict) -> bool:
    if "marketSize" not in data or not isinstance(data["marketSize"], str):
        return False
    if "trends" not in data or not isinstance(data["trends"], list):
        return False
    if not all(isinstance(item, str) for item in data["trends"]):
        return False
    if "segments" not in data or not isinstance(data["segments"], list):
        return False
    if not data["segments"] or not all(_is_valid_segment(s) for s in data["segments"]):
        return False
    return True


def analyze_market_opportunity(
    idea: str, target_customer: str, problem: str, results: list
) -> dict:
    """Falls back to a deterministic, evidence-based summary (see
    deterministic_fallback.py) whenever the LLM call itself fails (e.g. no
    API key configured, every fallback model rate limited) or its output
    doesn't parse into a valid shape, instead of raising and leaving this
    section entirely blank. The fallback result carries `"degraded": True`
    so callers/UI can distinguish it from a full AI-reasoned result - it is
    never silently indistinguishable from one.
    """
    context = _build_context(results)

    try:
        crew_output = kickoff_with_fallback(
            lambda model: _build_market_crew(idea, target_customer, problem, context, model)
        )

        # Search for valid JSON directly rather than rejecting the whole
        # response for containing extra text first - this model often
        # rambles through a visible scratchpad but still lands on a
        # correct, well-shaped JSON object by the end of it.
        data = extract_json_object(crew_output.raw, _is_valid_shape)
        if data is None:
            logger.warning("Market opportunity: no valid JSON found in output: %r", crew_output.raw)
            raise ValueError("Market opportunity analysis did not return a valid, parseable result.")

        data["trends"] = data["trends"][:_MAX_TRENDS]
        data["segments"] = data["segments"][:_MAX_SEGMENTS]
        # Phase 2 stretch feature - filled in by the opportunity_score graph node
        # after this agent returns, so stub it here for a stable shape.
        data.setdefault("opportunityScore", 0)
        return data
    except Exception:
        logger.warning(
            "Market opportunity: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        return deterministic_market_opportunity(idea, target_customer, problem, results)
