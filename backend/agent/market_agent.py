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

from . import events
from .deterministic_fallback import deterministic_market_opportunity
from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback, primary_for, AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER
from .verification import audit, strip_unsupported, verify_claims
from .prompts.loader import load_prompt
from .structured_output import (
    compact_sources,
    extract_inline_citations,
    extract_json_object,
    sanitize_source_ids,
    valid_source_ids,
)

logger = logging.getLogger(__name__)

# Not underscore-prefixed - graph.py's confidence dashboard imports this so
# its source-relevance lookup covers the same citation window market's
# trends/segments can actually cite (see _source_relevance_by_id).
MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 600  # was 300; advanced Tavily search returns longer, more relevant content
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
        backstory=load_prompt("market_analysis_system"),
        # Rebalanced to 750 (was 900, briefly tried 250 then 550). Market's
        # JSON schema (marketSize sentence + trends array + multi-field
        # segments) is the most verbose of the four agents and was
        # confirmed live to truncate into invalid JSON at 550, so it keeps
        # more headroom than mvp/gtm below even though all four still
        # collectively exceed Groq's ~1000 output-tokens/minute cap on the
        # primary model - the model-fallback chain (see llm.py) is the
        # actual safety net for whichever call(s) exceed the shared budget.
        llm=get_llm(max_tokens=750, model=model),
        max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
        max_iter=AGENT_MAX_ITER,
        verbose=False,
    )

    task = Task(
        description=load_prompt(
            "market_analysis_task",
            idea=idea,
            target_customer=target_customer or "not specified",
            problem=problem or "not specified",
            context=context,
        ),
        expected_output=load_prompt("market_analysis_output"),
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
    if not (
        isinstance(value, dict)
        and isinstance(value.get("text"), str)
        and bool(value["text"].strip())
        and valid_source_ids(value.get("sourceIds", []))
    ):
        return False
    # An estimated tier (SAM/SOM only - see _clean_tier) is allowed so long
    # as it states the assumption behind the number.
    if value.get("estimated") is True:
        assumptions = value.get("assumptions")
        return isinstance(assumptions, str) and bool(assumptions.strip())
    return True


_MAX_ASSUMPTION_CHARS = 220


def _clean_tier(name: str, value, valid_ids: set, tam_present: bool):
    """Normalise one tier. A sourced tier keeps its citations. An estimated
    tier (the model's own working from the TAM, no source states it) is kept
    only for SAM/SOM and only when a sourced-or-present TAM exists to work
    from; it carries no citations (it must never look grounded) and always
    keeps its stated assumption so the UI can show how the number was reached.
    TAM itself is never allowed to be an estimate.
    """
    if not isinstance(value, dict):
        return None
    if value.get("estimated") is True:
        assumptions = (value.get("assumptions") or "").strip()
        if name == "tam" or not tam_present or not assumptions:
            return None
        return {
            "text": value["text"].strip(),
            "sourceIds": [],
            "estimated": True,
            "assumptions": assumptions[:_MAX_ASSUMPTION_CHARS],
        }
    return {
        "text": value["text"].strip(),
        "sourceIds": sanitize_source_ids(value.get("sourceIds"), valid_ids),
    }


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
    idea: str, target_customer: str, problem: str, results: list, allow_local: bool = False
) -> dict:
    """Falls back to a deterministic, evidence-based summary (see
    deterministic_fallback.py) only once a local-model retry has also been
    tried (allow_local True) - before that, raises NeedsDeepAnalysisError so
    the caller can ask for an email instead of silently serving the weaker
    result. The fallback result carries `"degraded": True` so callers/UI
    can distinguish it from a full AI-reasoned result - it is never
    silently indistinguishable from one.
    """
    context, sources = _build_context(results)
    valid_ids = {source["sourceId"] for source in sources}

    try:
        crew_output = kickoff_with_fallback(
            lambda model: _build_market_crew(idea, target_customer, problem, context, model),
            primary=primary_for("market"),
            allow_local=allow_local,
            validate=lambda output: extract_json_object(output.raw, _is_valid_shape) is not None,
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
        # marketSize is free prose, so the model sometimes writes citations
        # into it as "[src-1]" / "【src-1】" instead of listing them. Pull
        # those out into marketSizeSourceIds so they render as real
        # citation markers, not raw text.
        size_text, inline_ids = extract_inline_citations(data["marketSize"])
        data["marketSize"] = size_text
        data["marketSizeSourceIds"] = sanitize_source_ids(
            [*(data.get("marketSizeSourceIds") if valid_source_ids(data.get("marketSizeSourceIds")) else []), *inline_ids],
            valid_ids,
        )
        data["tam"] = _clean_tier("tam", data.get("tam"), valid_ids, tam_present=True)
        for tier in ("sam", "som"):
            data[tier] = _clean_tier(tier, data.get(tier), valid_ids, tam_present=data["tam"] is not None)
        data["trends"] = [
            {"text": item["text"].strip(), "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids)}
            for item in data["trends"][:_MAX_TRENDS]
        ]
        data["segments"] = [
            {**segment, "sourceIds": sanitize_source_ids(segment.get("sourceIds"), valid_ids)}
            for segment in data["segments"][:_MAX_SEGMENTS]
        ]

        # Grounding verification (see verification.py) - sanitize above only
        # confirmed a cited sourceId exists; this confirms the cited source
        # actually supports the claim, and strips the citation (not the
        # claim) when it doesn't.
        snippets = {s["sourceId"]: s["snippet"] for s in sources}
        flat = (
            [{"text": data["marketSize"], "sourceIds": data["marketSizeSourceIds"]}]
            + ([{"text": data["tam"]["text"], "sourceIds": data["tam"]["sourceIds"]}] if data.get("tam") else [])
            + ([{"text": data["sam"]["text"], "sourceIds": data["sam"]["sourceIds"]}] if data.get("sam") else [])
            + ([{"text": data["som"]["text"], "sourceIds": data["som"]["sourceIds"]}] if data.get("som") else [])
            + data["trends"]
            + [{"text": s["painPoints"], "sourceIds": s["sourceIds"]} for s in data["segments"]]
        )
        supported = verify_claims(idea, flat, snippets, allow_local=allow_local)
        verified = strip_unsupported(flat, supported)
        data["verification"] = audit(flat, supported)
        data["marketSizeSourceIds"] = verified[0]["sourceIds"]
        cursor = 1
        for tier in ("tam", "sam", "som"):
            if data.get(tier):
                data[tier]["sourceIds"] = verified[cursor]["sourceIds"]
                cursor += 1
        for trend in data["trends"]:
            trend["sourceIds"] = verified[cursor]["sourceIds"]
            cursor += 1
        for segment in data["segments"]:
            segment["sourceIds"] = verified[cursor]["sourceIds"]
            cursor += 1

        # Phase 2 stretch feature - filled in by the opportunity_score graph node
        # after this agent returns, so stub it here for a stable shape.
        data.setdefault("opportunityScore", 0)
        return data
    except Exception as exc:
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "Market opportunity: LLM analysis unavailable, using deterministic evidence-based fallback",
            exc_info=True,
        )
        events.record("llm_fallback", node="market_opportunity", detail={"errorType": type(exc).__name__})
        return deterministic_market_opportunity(idea, target_customer, problem, results)
