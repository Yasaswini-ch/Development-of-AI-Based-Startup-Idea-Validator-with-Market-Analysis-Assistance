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

import json
import logging

from crewai import Agent, Crew, Process, Task

from .llm import get_llm, kickoff_with_fallback
from .output_guard import strip_reasoning

logger = logging.getLogger(__name__)

_MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 300
_MAX_SEGMENTS = 4
_MAX_TRENDS = 4


def _build_context(results: list) -> str:
    """Condense the real search results into a compact block of grounding
    text for the prompt - capped so we don't blow up the context window
    with everything retrieval.py fetched.
    """
    lines = []
    for r in results[:_MAX_SOURCES_IN_CONTEXT]:
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
        llm=get_llm(model=model),
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
            "niche if the sources indicate this) and growth trend.\n"
            "2. Up to 4 notable trends or adoption patterns.\n"
            "3. Up to 4 customer segments - for each, their pain points (what "
            "problem they're trying to solve), motivations (what they care "
            "about / why they'd buy), and buying behavior (how they decide or "
            "purchase, if the sources suggest anything about this).\n"
            "Do not invent statistics, segments, or behaviors that aren't "
            "supported by the sources - if buying behavior isn't evident from "
            "the sources, say so plainly rather than guessing."
        ),
        expected_output=(
            "A single JSON object, and nothing else - no markdown code fences, no "
            "explanation before or after it, no placeholder text. Fill in real "
            "content from the sources above. For example, for a different idea "
            "this might look like:\n"
            '{"marketSize": "The global market was valued at $2.1 billion in 2024 '
            'and is growing at 12% annually.", '
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


def _find_balanced_objects(text: str) -> list[str]:
    """Find every top-level {...} substring via brace counting, not just
    first-'{'-to-last-'}' (which breaks if the model wraps its real answer
    in explanatory text containing its own braces, e.g. a markdown code
    fence example). Returns them in the order they appear.
    """
    objects = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    objects.append(text[start : i + 1])
    return objects


def _extract_json(text: str) -> dict | None:
    """Try every balanced {...} substring, last-to-first, and return the
    first one that's both valid JSON and has the right shape. This
    recovers the real answer even when the model buries it in a rambling
    scratchpad, as long as it does eventually produce valid JSON somewhere.
    """
    for candidate in reversed(_find_balanced_objects(text)):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and _is_valid_shape(data):
            return data
    return None


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
    """Raises on any failure - a crew error (e.g. Groq rate limit) or output that
    doesn't parse/validate - rather than silently returning empty trends/segments.

    Unlike an empty competitors list (a valid outcome - see competitor_agent.py),
    a market opportunity with zero segments isn't a legitimate "nothing to find"
    result - it means the call failed. Raising here lets the caller
    (agent/graph.py's market_opportunity_node) catch it and set
    marketOpportunity=null + errors.marketOpportunity, which is what reaches the
    frontend's "analysis wasn't available" state instead of a silent, misleading
    "not enough data" placeholder that looked identical to a real weak result.
    """
    context = _build_context(results)

    crew_output = kickoff_with_fallback(
        lambda model: _build_market_crew(idea, target_customer, problem, context, model)
    )
    candidate_text = strip_reasoning(crew_output.raw)

    # Search for valid JSON directly rather than rejecting the whole
    # response for containing extra text first - this model often
    # rambles through a visible scratchpad but still lands on a
    # correct, well-shaped JSON object by the end of it.
    data = _extract_json(candidate_text)
    if data is None:
        logger.warning("Market opportunity: no valid JSON found in output: %r", candidate_text)
        raise ValueError("Market opportunity analysis did not return a valid, parseable result.")

    data["trends"] = data["trends"][:_MAX_TRENDS]
    data["segments"] = data["segments"][:_MAX_SEGMENTS]
    # Phase 2 stretch feature - filled in by the opportunity_score graph node
    # after this agent returns, so stub it here for a stable shape.
    data.setdefault("opportunityScore", 0)
    return data
