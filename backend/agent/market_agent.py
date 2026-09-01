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

from crewai import Agent, Crew, Process, Task

from .llm import get_llm
from .output_guard import looks_like_leaked_reasoning, strip_reasoning

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
            "explanation before or after it. Shape:\n"
            '{"industrySize": "one sentence describing market size/growth if known, '
            'or \'not enough data\' if not", '
            '"trends": ["short trend 1", "short trend 2", "..."], '
            '"targetSegments": ["segment 1", "segment 2", "..."]}\n'
            "Keep each list to at most 4 items."
        ),
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def _extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


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

        if not looks_like_leaked_reasoning(candidate_text, max_len=1500):
            data = _extract_json(candidate_text)
            if data and _is_valid_shape(data):
                data["trends"] = data["trends"][:4]
                data["targetSegments"] = data["targetSegments"][:4]
                return data
    except Exception:
        pass

    return _fallback(results)
