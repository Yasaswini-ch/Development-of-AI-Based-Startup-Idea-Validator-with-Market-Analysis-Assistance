"""
Market Opportunity & Customer Segmentation Analysis Agent (Milestone 2).

Takes the Web Search Agent's results and reasons about industry size,
trends, and target customer segments - grounded in that real data, not
invented. This is the second stage of the pipeline: web_search runs first,
and its results are passed in here (context passing between agents).

Like the Web Search Agent, this deliberately avoids CrewAI's
output_pydantic/function-calling conversion for structured output - that
proved unreliable with our tested Groq model in Milestone 1 (repeated
"tool_use_failed" errors, then silent fallback to garbage text). Instead
the task asks for plain JSON in its answer, which we parse and validate
ourselves, with a safe fallback if parsing fails or the output looks like
a leaked reasoning trace.
"""

import json
import logging

from crewai import Agent, Crew, Process, Task

from .llm import get_llm
from .output_guard import strip_reasoning

logger = logging.getLogger(__name__)

_MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 300


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


def _build_market_crew(idea: str, target_customer: str, problem: str, context: str) -> Crew:
    analyst = Agent(
        role="Market Opportunity & Customer Segmentation Analyst",
        goal="Evaluate industry size, trends, and target customer segments for a startup idea",
        backstory=(
            "A market analyst who only reasons from the evidence provided, "
            "never inventing statistics or segments that aren't supported by "
            "the given sources."
        ),
        llm=get_llm(),
        verbose=False,
    )

    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Target customer: {target_customer or 'not specified'}\n"
            f"Problem being solved: {problem or 'not specified'}\n\n"
            "Here are real, current web search results about this idea's market:\n"
            f"{context}\n\n"
            "Based only on the information above, analyze the market opportunity. "
            "Do not invent statistics that aren't supported by the sources."
        ),
        expected_output=(
            "A single JSON object, and nothing else - no markdown code fences, no "
            "explanation before or after it, no placeholder text. Fill in real "
            "content from the sources above. For example, for a different idea "
            "this might look like:\n"
            '{"industrySize": "The market was valued at $2.1 billion in 2024 and is '
            'growing at 12% annually.", '
            '"trends": ["Rising demand for subscription-based delivery", '
            '"Increased focus on eco-friendly packaging"], '
            '"targetSegments": ["Urban millennials", "Budget-conscious families"]}\n'
            "Use at most 4 items per list, grounded only in the sources given to you."
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


def _is_valid_shape(data: dict) -> bool:
    if "industrySize" not in data or not isinstance(data["industrySize"], str):
        return False
    for key in ("trends", "targetSegments"):
        if key not in data or not isinstance(data[key], list):
            return False
        if not all(isinstance(item, str) for item in data[key]):
            return False
    return True


def _fallback(results: list) -> dict:
    return {
        "industrySize": (
            "Not enough grounded data to estimate market size."
            if not results
            else "See the search results below for market size signals."
        ),
        "trends": [],
        "targetSegments": [],
    }


def analyze_market_opportunity(
    idea: str, target_customer: str, problem: str, results: list
) -> dict:
    context = _build_context(results)

    try:
        crew = _build_market_crew(idea, target_customer, problem, context)
        crew_output = crew.kickoff()
        candidate_text = strip_reasoning(crew_output.raw)

        # Search for valid JSON directly rather than rejecting the whole
        # response for containing extra text first - this model often
        # rambles through a visible scratchpad but still lands on a
        # correct, well-shaped JSON object by the end of it.
        data = _extract_json(candidate_text)
        if data is None:
            logger.warning("Market opportunity: no valid JSON found in output: %r", candidate_text)
        else:
            data["trends"] = data["trends"][:4]
            data["targetSegments"] = data["targetSegments"][:4]
            return data
    except Exception:
        logger.exception("Market opportunity crew failed")

    return _fallback(results)
