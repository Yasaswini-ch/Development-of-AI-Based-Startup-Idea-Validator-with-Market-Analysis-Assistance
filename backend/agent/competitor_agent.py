"""
Competitor Discovery & Comparison Agent (Milestone 2).

Takes the Web Search Agent's results and identifies key competitors, what
each offers, and where there might be a gap the startup idea could fill -
grounded in that real data, not invented. Runs after the Web Search Agent
(context passing between agents), alongside the Market Opportunity Agent.

Output shape matches the team contract in docs/milestone2-plan.md exactly,
so Yalene's orchestration and Anu Kumari's frontend can build against it
without waiting on this file:

    {
      "competitors": [
        {
          "name": str,
          "offering": str,           # one-line description
          "url": str,
          "gap": str,                # what this idea could do differently/better
          "estimatedPrice": "low" | "mid" | "high" | "unknown",
          "featureBreadth": "narrow" | "moderate" | "broad" | "unknown",
        }
      ]
    }

`estimatedPrice`/`featureBreadth` are LLM-estimated categorical guesses,
not verified data - the frontend should label them as such. They're
included from day one (rather than added in a later pass) so the shape
never changes underneath consumers; the model is told to say "unknown"
rather than guess when the sources don't support an estimate.

Same reliability pattern as agent/market_agent.py: no tools (reasons over
data given to it, doesn't re-search), plain JSON in the answer rather than
CrewAI's output_pydantic (unreliable with our tested Groq model), and JSON
recovered via balanced-brace scanning so a rambling scratchpad before the
real answer doesn't sink the whole response.
"""

import json
import logging

from crewai import Agent, Crew, Process, Task

from .llm import get_llm
from .output_guard import strip_reasoning

logger = logging.getLogger(__name__)

_MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 300
_MAX_COMPETITORS = 4
_PRICE_LEVELS = {"low", "mid", "high", "unknown"}
_BREADTH_LEVELS = {"narrow", "moderate", "broad", "unknown"}


def _build_context(results: list) -> str:
    lines = []
    for r in results[:_MAX_SOURCES_IN_CONTEXT]:
        snippet = (r.get("snippet") or "")[:_MAX_SNIPPET_LEN]
        url = r.get("url", "")
        lines.append(f"- {r.get('title', '')} ({url}): {snippet}")
    return "\n".join(lines) if lines else "No search results were available."


def _build_competitor_crew(idea: str, target_customer: str, problem: str, context: str) -> Crew:
    analyst = Agent(
        role="Competitor Discovery & Comparison Analyst",
        goal=(
            "Identify real competitors from the search results, summarize what "
            "each offers, and find gaps a new entrant could fill"
        ),
        backstory=(
            "A competitive analyst who only names competitors, URLs, and "
            "features that actually appear in the evidence provided, never "
            "inventing companies or capabilities. Writes for a founder "
            "deciding how to differentiate, not a directory listing."
        ),
        llm=get_llm(),
        verbose=False,
    )

    task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Target customer: {target_customer or 'not specified'}\n"
            f"Problem being solved: {problem or 'not specified'}\n\n"
            "Here are real, current web search results about this idea's market "
            "(each with its source URL):\n"
            f"{context}\n\n"
            "Based only on the information above, identify up to 4 real "
            "competitors (direct or indirect) that appear in the sources. For "
            "each, give:\n"
            "- name: the competitor's actual name\n"
            "- offering: their core offering in one line\n"
            "- url: the exact source URL from above where this competitor was "
            "found (copy it exactly, don't invent one)\n"
            "- gap: one specific weak spot, missing feature, or underserved "
            "user segment this competitor doesn't address\n"
            "- estimatedPrice: \"low\", \"mid\", or \"high\" only if pricing is "
            "mentioned in the sources, otherwise \"unknown\"\n"
            "- featureBreadth: \"narrow\", \"moderate\", or \"broad\" based on "
            "how many features/use-cases the sources describe, otherwise "
            "\"unknown\"\n"
            "Do not invent competitor names, URLs, features, or gaps that "
            "aren't supported by the sources - use \"unknown\" rather than "
            "guessing when something isn't evident."
        ),
        expected_output=(
            "A single JSON object, and nothing else - no markdown code fences, no "
            "explanation before or after it, no placeholder text. Fill in real "
            "content from the sources above. For example, for a different idea "
            "this might look like:\n"
            '{"competitors": ['
            '{"name": "Acme Meal Co", '
            '"offering": "Subscription meal kits with pre-portioned ingredients delivered weekly.", '
            '"url": "https://example.com/acme-meal-co", '
            '"gap": "No options for large families or bulk ordering.", '
            '"estimatedPrice": "mid", '
            '"featureBreadth": "moderate"}, '
            '{"name": "FreshBox", '
            '"offering": "Budget grocery delivery focused on staple ingredients.", '
            '"url": "https://example.com/freshbox", '
            '"gap": "Limited recipe guidance or meal planning support.", '
            '"estimatedPrice": "low", '
            '"featureBreadth": "narrow"}'
            "]}\n"
            "Use at most 4 competitors, grounded only in the sources given to you."
        ),
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def _find_balanced_objects(text: str) -> list[str]:
    """Find every top-level {...} substring via brace counting, not just
    first-'{'-to-last-'}' (which breaks if the model wraps its real answer
    in explanatory text containing its own braces).
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
    first one that's both valid JSON and has the right shape - recovers the
    real answer even when the model rambles through a scratchpad first.
    """
    for candidate in reversed(_find_balanced_objects(text)):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and _is_valid_shape(data):
            return data
    return None


def _is_valid_competitor(item) -> bool:
    if not isinstance(item, dict):
        return False
    required_strings = ("name", "offering", "url", "gap")
    if not all(isinstance(item.get(key), str) for key in required_strings):
        return False
    if item.get("estimatedPrice") not in _PRICE_LEVELS:
        return False
    if item.get("featureBreadth") not in _BREADTH_LEVELS:
        return False
    return True


def _is_valid_shape(data: dict) -> bool:
    if "competitors" not in data or not isinstance(data["competitors"], list):
        return False
    if not data["competitors"] or not all(_is_valid_competitor(c) for c in data["competitors"]):
        return False
    return True


def _fallback() -> dict:
    return {"competitors": []}


def analyze_competitors(idea: str, target_customer: str, problem: str, results: list) -> dict:
    context = _build_context(results)

    try:
        crew = _build_competitor_crew(idea, target_customer, problem, context)
        crew_output = crew.kickoff()
        candidate_text = strip_reasoning(crew_output.raw)

        data = _extract_json(candidate_text)
        if data is None:
            logger.warning("Competitor analysis: no valid JSON found in output: %r", candidate_text)
        else:
            data["competitors"] = data["competitors"][:_MAX_COMPETITORS]
            return data
    except Exception:
        logger.exception("Competitor analysis crew failed")

    return _fallback()
