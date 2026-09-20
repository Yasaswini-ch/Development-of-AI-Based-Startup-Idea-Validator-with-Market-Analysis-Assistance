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

Milestone 4 / Track A: trends and segments now carry a "sourceIds" field,
same {"text", "sourceIds"} per-claim shape swot_agent.py already
established (docs/unique-features-plan.md §5.1) - see
_is_valid_trend/_is_valid_segment below. marketSize stays a plain string
(it's one narrative sentence, not a list of discrete claims, so there's no
SWOT-equivalent per-item shape to mirror there).

Milestone 4 follow-up: tam/sam/som are structured alongside marketSize -
each is either a {"text", "sourceIds"} claim (see _is_valid_tier below) or
null when the sources don't support that specific figure. Kept separate
from marketSize (which stays a free narrative sentence) rather than
replacing it, since existing callers (opportunity_score.py, the frontend)
already depend on marketSize's shape and semantics.
"""

import logging

from crewai import Agent, Crew, Process, Task

from .deterministic_fallback import deterministic_market_opportunity
from .llm import get_llm, kickoff_with_fallback
from .structured_output import compact_sources, extract_json_object, sanitize_source_ids, valid_source_ids

logger = logging.getLogger(__name__)

# Not underscore-prefixed - graph.py's confidence dashboard imports this so
# its source-relevance lookup covers the same citation window market's
# trends/segments can actually cite (see _source_relevance_by_id).
MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 300
_MAX_SEGMENTS = 4
_MAX_TRENDS = 4


def _build_context(results: list) -> tuple[str, list[dict]]:
    """Condense the real search results into a compact block of grounding
    text for the prompt, tagged with the sourceId the model must cite - and
    return the exact source list shown, so the caller can build the same
    valid_ids set used to sanitize the model's sourceIds afterwards.

    compact_sources() assigns "src-N" purely by position in `results` - the
    same convention swot_agent.py and graph.py's confidence dashboard rely
    on - so it's called here on the full, un-reordered `results` list first
    (never on a re-sorted copy) to guarantee "src-N" means the same source
    everywhere in the app, not just within this agent's own prompt.

    Market-size prioritization (the "don't crowd out Market size & trends
    results" fix, confirmed by the same live failure as
    competitor_agent.py's _build_context) is still applied, but only to
    decide which of those already-canonically-numbered sources get shown in
    this prompt - it no longer changes what "src-N" refers to.
    """
    all_sources = compact_sources(results, limit=len(results) or 1, snippet_chars=_MAX_SNIPPET_LEN)
    if not all_sources:
        return "No search results were available.", []

    market_sources = [s for s in all_sources if s.get("angle") == "Market size & trends"]
    other_sources = [s for s in all_sources if s.get("angle") != "Market size & trends"]
    shown = (market_sources + other_sources)[:MAX_SOURCES_IN_CONTEXT]

    lines = [f"- [{s['sourceId']}] {s.get('title', '')}: {s.get('snippet', '')}" for s in shown]
    return "\n".join(lines), shown


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
            "Here are real, current web search results about this idea's market. "
            "Each one is tagged with a sourceId like [src-1]:\n"
            f"{context}\n\n"
            "Based only on the information above, analyze:\n"
            "1. Market size (state whether the figures are global, regional, or "
            "niche if the sources indicate this) and growth trend. Include TAM, "
            "SAM, or CAGR only when the provided sources explicitly support those "
            "figures; otherwise state that they are not clear from the sources.\n"
            "1b. Separately, TAM (Total Addressable Market), SAM (Serviceable "
            "Addressable Market), and SOM (Serviceable Obtainable Market) as three "
            "distinct figures, each with a \"sourceIds\" array the same way as for "
            "trends below. Set any of the three to null (not a guessed number) "
            "whenever the sources don't explicitly support that specific figure - "
            "never derive one tier's number from another or estimate a plausible-"
            "looking value.\n"
            "2. Up to 4 notable trends or adoption patterns. Each trend needs a "
            "\"sourceIds\" array citing the sourceId(s) of the source(s) shown "
            "above that it's grounded in - use an empty array only when a trend "
            "is a structural observation not tied to a specific source, never "
            "invent a sourceId that isn't shown above.\n"
            "3. Up to 4 customer segments - for each, their pain points (what "
            "problem they're trying to solve), motivations (what they care "
            "about / why they'd buy), buying behavior (how they decide or "
            "purchase, if the sources suggest anything about this), and a "
            "\"sourceIds\" array the same way as for trends.\n"
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
            '"tam": {"text": "$2.1 billion global market (2024)", "sourceIds": ["src-1"]}, '
            '"sam": null, '
            '"som": null, '
            '"trends": [{"text": "Rising demand for subscription-based delivery", "sourceIds": ["src-1"]}, '
            '{"text": "Increased focus on eco-friendly packaging", "sourceIds": []}], '
            '"segments": ['
            '{"segment": "Urban millennials", '
            '"painPoints": "Limited time to research and compare options", '
            '"motivations": "Convenience and sustainability credentials", '
            '"buyingBehavior": "Research online, prefer subscription models over one-off purchases", '
            '"sourceIds": ["src-1"]}, '
            '{"segment": "Budget-conscious families", '
            '"painPoints": "Existing options are too expensive for regular use", '
            '"motivations": "Value for money without sacrificing quality", '
            '"buyingBehavior": "Not clear from the sources", '
            '"sourceIds": []}'
            "]}\n"
            "Use at most 4 items in trends and 4 objects in segments, grounded "
            "only in the sources given to you, and never cite a sourceId that "
            "wasn't shown to you above."
        ),
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def _is_valid_trend(item) -> bool:
    """A trend is {"text": str, "sourceIds": [str]} - the same per-claim
    shape as swot_agent.py's items - not a bare string. sourceIds defaults
    to an empty list when the key is missing, same leniency swot_agent.py
    applies, since the field is still always present on the sanitized output.
    """
    return (
        isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and bool(item["text"].strip())
        and valid_source_ids(item.get("sourceIds", []))
    )


def _is_valid_tier(value) -> bool:
    """A TAM/SAM/SOM tier is either null (the sources don't support that
    specific figure) or a {"text", "sourceIds"} claim, same per-claim shape
    as trends/segments - never a bare number or string, since every figure
    still needs to cite where it came from.
    """
    if value is None:
        return True
    return (
        isinstance(value, dict)
        and isinstance(value.get("text"), str)
        and bool(value["text"].strip())
        and valid_source_ids(value.get("sourceIds", []))
    )


def _is_valid_segment(item) -> bool:
    if not isinstance(item, dict):
        return False
    required = ("segment", "painPoints", "motivations", "buyingBehavior")
    if not all(isinstance(item.get(key), str) for key in required):
        return False
    return valid_source_ids(item.get("sourceIds", []))


def _is_valid_shape(data: dict) -> bool:
    if "marketSize" not in data or not isinstance(data["marketSize"], str):
        return False
    for tier in ("tam", "sam", "som"):
        if not _is_valid_tier(data.get(tier)):
            return False
    if "trends" not in data or not isinstance(data["trends"], list):
        return False
    if not all(_is_valid_trend(item) for item in data["trends"]):
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
    context, sources = _build_context(results)
    valid_ids = {source["sourceId"] for source in sources}

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

        # Never let a hallucinated sourceId (one the model invented, or one
        # that was shown but isn't actually in this run's evidence) reach
        # the API response - same sanitize-after-parse step swot_agent.py
        # already does.
        for tier in ("tam", "sam", "som"):
            value = data.get(tier)
            if isinstance(value, dict):
                data[tier] = {
                    "text": value["text"].strip(),
                    "sourceIds": sanitize_source_ids(value.get("sourceIds"), valid_ids),
                }
            else:
                data[tier] = None
        data["trends"] = [
            {"text": item["text"].strip(), "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["trends"][:_MAX_TRENDS]
        ]
        data["segments"] = [
            {**segment, "sourceIds": sanitize_source_ids(segment.get("sourceIds"), valid_ids)}
            for segment in data["segments"][:_MAX_SEGMENTS]
        ]
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
