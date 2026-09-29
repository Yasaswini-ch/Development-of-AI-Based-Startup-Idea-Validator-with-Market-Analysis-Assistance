import logging
import time
from datetime import datetime, timezone
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from . import events, metrics, retrieval
from .action_plan import generate_action_plan
from .assumption_agent import analyze_assumptions
from .competitor_agent import analyze_competitors
from .contradiction_detector import detect_contradictions
from .experiment_generator import generate_experiments
from .gtm_agent import analyze_gtm
from .llm import NeedsDeepAnalysisError
from .market_agent import MAX_SOURCES_IN_CONTEXT, analyze_market_opportunity
from .mvp_agent import analyze_mvp
from .revenue_agent import analyze_revenue_models
from .opportunity_score import calculate_opportunity_score
from .structured_output import compact_sources
from .swot_agent import analyze_swot
from .commercial_model import build_commercial_model
from .delivery_roadmap import build_delivery_roadmap
from .strategic_wedge import build_strategic_wedges
from .verdict import build_verdict
from .viability_score import calculate_market_viability, calculate_viability_index
from .voice_of_market import (
    extract_voice_of_market,
    extract_voice_of_owner,
    summarize_voice_of_market,
    summarize_voice_of_owner,
)
from .white_space import analyze_white_space

logger = logging.getLogger(__name__)

# state["error"] value set by any strategy node that catches
# NeedsDeepAnalysisError - main.py checks for this exact string to decide
# whether to ask for an email instead of returning a normal 502, since it
# means "every cloud model is exhausted," not "the request itself failed."
NEEDS_DEEP_ANALYSIS = "NEEDS_DEEP_ANALYSIS"


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

def _friendly_error_message(exc: Exception) -> str:
    """Convert internal exceptions into user-friendly error messages."""
    text = str(exc)

    if "RateLimitError" in text or "rate_limit" in text:
        return "This analysis hit a temporary usage limit. Please try again in a moment."

    return "This analysis couldn't be completed for this request. Please try again."


def _record_node_failure(node: str, exc: Exception) -> None:
    """Shared by every node's except-block: bumps the in-process
    node.{node}.failure counter (agent/metrics.py, current-total-only) and
    appends a durable "pipeline_error" event (agent/events.py) so GET
    /admin/platform-metrics' error log has real node/error-type rows to
    show, not just a live-total percentage.
    """
    metrics.increment(f"node.{node}.failure")
    events.record("pipeline_error", node=node, detail={"errorType": type(exc).__name__})


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

def _build_summary(idea: str, results: list) -> str:
    """Build a summary directly from web-search results."""

    if not results:
        return f'No market data found yet for "{idea}".'

    angles = sorted({r.get("angle", "") for r in results} - {""})
    coverage = ", ".join(angles) if angles else "the web"

    return (
        f'Found {len(results)} relevant sources for "{idea}", '
        f"covering {coverage}. See the results below for details."
    )


# --------------------------------------------------
# PIPELINE STATE
# --------------------------------------------------

def _merge_error(current: str | None, update: str | None) -> str | None:
    """Reducer for the "error" channel.

    mvp_recommendation and gtm_strategy now run as parallel branches off
    viability_score (see build_pipeline below) instead of one after the
    other. Both can independently set "error" to NEEDS_DEEP_ANALYSIS on
    NeedsDeepAnalysisError, and LangGraph's default per-key channel only
    accepts one write per step - two concurrent writes raise even when, as
    here, they'd carry the same value. Prefer whichever write is truthy so
    either branch alone, or both together, resolve the same way a single
    sequential write always did.
    """
    return update or current


def _merge_errors(current: dict | None, update: dict | None) -> dict:
    """Reducer for the "errors" channel, needed for the same reason as
    _merge_error above: mvp_recommendation and gtm_strategy can now fail
    independently in the same step, each recording its own key.
    """
    return {**(current or {}), **(update or {})}


class PipelineState(TypedDict, total=False):
    idea: str
    targetCustomer: str
    problem: str

    # Track G.2 - "quick" skips every Milestone 3/4 strategy node (SWOT,
    # viability, MVP, GTM, contradictions, experiments, action plan) and
    # returns only core market validation; "deep" (the default) runs the
    # full pipeline unchanged. Checked node-by-node, same pattern each node
    # already uses to skip itself when state.get("error") is set.
    mode: str

    # True only once an email address is on file for this request (see
    # main.py's /validate) - lets every LLM-backed strategy node retry via
    # the local Ollama model instead of raising NeedsDeepAnalysisError when
    # every cloud model is exhausted. False on a request's first attempt,
    # before main.py knows whether deep analysis will even be needed.
    allowLocalLlm: bool

    summary: str
    results: list

    # Cross-source confidence
    confidence: dict

    # Market analysis
    marketOpportunity: dict

    # Competitor analysis
    competitors: dict

    # Evidence-backed opportunity gaps
    whiteSpace: dict

    # Milestone 3 strategy artifacts
    swot: dict
    mvp: dict
    gtm: dict

    # Track B: cross-artifact contradiction flags
    contradictions: list

    # Track C: validation experiments and founder action plan
    experiments: list
    actionPlan: dict

    # Market Viability Score
    marketViability: dict

    # Novel features: assumption tracker + revenue model suggester
    assumptions: dict
    revenueModels: dict

    # Go / no-go verdict (recombines the scores above, no LLM call)
    verdict: dict

    # Errors
    error: Annotated[str | None, _merge_error]
    errors: Annotated[dict, _merge_errors]


# --------------------------------------------------
# MILESTONE 1: WEB SEARCH
# --------------------------------------------------

def web_search_node(state: PipelineState) -> PipelineState:
    """Collect real web-search results."""

    logger.info("[web_search] START")

    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")

    try:
        results = retrieval.collect(
            idea,
            target_customer,
            problem,
        )

    except Exception as exc:
        logger.exception("[web_search] FAILED")
        metrics.increment("node.web_search.failure")

        return {
            **state,
            "error": str(exc),
        }

    logger.info(
        "[web_search] COMPLETE - %d results",
        len(results),
    )
    metrics.increment("node.web_search.success")

    return {
        **state,
        "summary": _build_summary(idea, results),
        "results": results,
    }


# --------------------------------------------------
# SASHI FEATURE
# CROSS-SOURCE CONFIDENCE INDICATOR
# --------------------------------------------------

def confidence_node(state: PipelineState) -> PipelineState:
    """
    Calculate cross-source confidence from the relevance scores
    already produced by retrieval.collect().

    Example:
        3 / 5 sources agree

    The calculation is based on the existing search results and
    does not require another LLM call.
    """

    logger.info("[confidence] START")

    if state.get("error"):
        logger.warning(
            "[confidence] Skipped because web search failed"
        )
        return state

    results = state.get("results", [])

    if not results:
        logger.warning(
            "[confidence] No search results available"
        )

        return {
            **state,
            "confidence": {
                "agreeingSources": 0,
                "totalSources": 0,
                "percentage": 0,
                "label": "0/0 sources agree",
            },
        }

    # Group results by angle.
    # This keeps the confidence calculation useful even if
    # retrieval returns several different research angles.
    angles = {}

    for result in results:
        angle = result.get("angle", "Sources")

        if angle not in angles:
            angles[angle] = []

        angles[angle].append(result)

    # Calculate confidence separately for each angle.
    per_angle = {}

    for angle, items in angles.items():
        scored_items = [
            item
            for item in items
            if isinstance(item.get("score"), (int, float))
        ]

        total_sources = len(items)

        if not scored_items:
            per_angle[angle] = {
                "agreeingSources": 0,
                "totalSources": total_sources,
                "percentage": 0,
                "label": f"0/{total_sources} sources agree",
            }
            continue

        # A relevance score >= 0.5 is considered a meaningful
        # supporting source.
        agreeing_sources = sum(
            1
            for item in scored_items
            if item.get("score", 0) >= 0.5
        )

        scored_total = len(scored_items)

        percentage = round(
            (agreeing_sources / scored_total) * 100
        )

        per_angle[angle] = {
            "agreeingSources": agreeing_sources,
            "totalSources": scored_total,
            "percentage": percentage,
            "label": f"{agreeing_sources}/{scored_total} sources agree",
        }

    # Overall confidence across all scored sources.
    scored_results = [
        result
        for result in results
        if isinstance(result.get("score"), (int, float))
    ]

    total_scored = len(scored_results)

    agreeing_total = sum(
        1
        for result in scored_results
        if result.get("score", 0) >= 0.5
    )

    if total_scored:
        overall_percentage = round(
            (agreeing_total / total_scored) * 100
        )
    else:
        overall_percentage = 0

    confidence = {
        "agreeingSources": agreeing_total,
        "totalSources": total_scored,
        "percentage": overall_percentage,
        "label": f"{agreeing_total}/{total_scored} sources agree",
        "perAngle": per_angle,
    }

    logger.info(
        "[confidence] COMPLETE - %s",
        confidence["label"],
    )

    return {
        **state,
        "confidence": confidence,
    }


# --------------------------------------------------
# MILESTONE 2: MARKET OPPORTUNITY
# --------------------------------------------------

def market_opportunity_node(state: PipelineState) -> PipelineState:
    """Market Opportunity & Customer Segmentation Analysis."""

    logger.info("[market_opportunity] START")

    if state.get("error"):
        logger.warning(
            "[market_opportunity] Skipped because web search failed"
        )
        return state

    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")
    results = state.get("results", [])

    try:
        market_opportunity = analyze_market_opportunity(
            idea,
            target_customer,
            problem,
            results,
            allow_local=state.get("allowLocalLlm", False),
        )

        # Pillar 1: verbatim excerpts copied from the search snippets (no
        # LLM call - see voice_of_market.py), attached here so they sit on
        # the deterministic fallback result too, not only the LLM one.
        if isinstance(market_opportunity, dict):
            market_opportunity = {
                **market_opportunity,
                "voiceOfMarket": extract_voice_of_market(results),
                "voiceOfMarketSummary": summarize_voice_of_market(results),
                "voiceOfOwner": extract_voice_of_owner(results),
                "voiceOfOwnerSummary": summarize_voice_of_owner(results),
            }

        logger.info("[market_opportunity] COMPLETE")
        metrics.increment("node.market_opportunity.success")

        return {
            **state,
            "marketOpportunity": market_opportunity,
        }

    except NeedsDeepAnalysisError as exc:
        logger.warning("[market_opportunity] Needs deep analysis - short-circuiting pipeline")
        _record_node_failure("market_opportunity", exc)
        return {**state, "error": NEEDS_DEEP_ANALYSIS}

    except Exception as exc:
        logger.exception("[market_opportunity] FAILED")
        _record_node_failure("market_opportunity", exc)

        errors = {
            **state.get("errors", {}),
            "marketOpportunity": _friendly_error_message(exc),
        }

        return {
            **state,
            "marketOpportunity": None,
            "errors": errors,
        }


# --------------------------------------------------
# MILESTONE 2: COMPETITOR DISCOVERY
# --------------------------------------------------

def competitor_discovery_node(state: PipelineState) -> PipelineState:
    """Competitor Discovery & Comparison Agent."""

    logger.info("[competitor_discovery] START")

    if state.get("error"):
        logger.warning(
            "[competitor_discovery] Skipped because web search failed"
        )
        return state

    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")
    results = state.get("results", [])

    try:
        # Competitor discovery always runs the LLM profiling pass (for the
        # comparison matrix and idea-specific gap analysis) regardless of
        # pipeline mode - it fails silently back to NER-only on quota issues.
        competitors = analyze_competitors(
            idea,
            target_customer,
            problem,
            results,
            profile=True,
            allow_local=state.get("allowLocalLlm", False),
        )

        logger.info("[competitor_discovery] COMPLETE")
        metrics.increment("node.competitor_discovery.success")

        return {
            **state,
            "competitors": competitors,
        }

    except Exception as exc:
        logger.exception("[competitor_discovery] FAILED")
        _record_node_failure("competitor_discovery", exc)

        errors = {
            **state.get("errors", {}),
            "competitors": _friendly_error_message(exc),
        }

        return {
            **state,
            "competitors": None,
            "errors": errors,
        }


# --------------------------------------------------
# SASHI'S MILESTONE 2 FEATURE
# OPPORTUNITY SCORE
# --------------------------------------------------

def opportunity_score_node(state: PipelineState) -> PipelineState:
    """
    Calculate the Opportunity Score using:

    - Market Size
    - Market Growth / Trends
    - Competitor Density

    Final score: 0-100
    """

    logger.info("[opportunity_score] START")

    if state.get("error"):
        logger.warning(
            "[opportunity_score] Skipped because web search failed"
        )
        return state

    market_opportunity = state.get("marketOpportunity")
    competitors = state.get("competitors")
    results = state.get("results", [])

    # Do not generate a fake score if market analysis failed.
    if market_opportunity is None:
        logger.warning(
            "[opportunity_score] Skipped because marketOpportunity is None"
        )
        return state

    try:
        score = calculate_opportunity_score(
            market_opportunity,
            competitors,
            results,
        )

        # Attach score to market opportunity response
        market_opportunity["opportunityScore"] = score

        logger.info(
            "[opportunity_score] COMPLETE - score=%s",
            score,
        )
        metrics.increment("node.opportunity_score.success")

    except Exception as exc:
        logger.exception("[opportunity_score] FAILED")
        _record_node_failure("opportunity_score", exc)

        # Safe fallback
        market_opportunity["opportunityScore"] = 0

    return {
        **state,
        "marketOpportunity": market_opportunity,
    }


# --------------------------------------------------
# MILESTONE 2: WHITE-SPACE ANALYSIS
# --------------------------------------------------

def white_space_node(state: PipelineState) -> PipelineState:
    """Reuse pipeline artifacts to identify opportunity gaps without an LLM."""

    logger.info("[white_space] START")

    if state.get("error"):
        logger.warning("[white_space] Skipped because web search failed")
        return state

    try:
        white_space = analyze_white_space(
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("results", []),
        )
    except Exception as exc:
        logger.exception("[white_space] FAILED")
        _record_node_failure("white_space", exc)
        errors = {
            **state.get("errors", {}),
            "whiteSpace": _friendly_error_message(exc),
        }
        return {
            **state,
            "whiteSpace": None,
            "errors": errors,
        }

    # Pillar 4: 5-vector strategic wedge blueprints, deterministic (see
    # strategic_wedge.py) - own try/except so a bug here can't take down
    # the opportunity-gap result already computed above.
    try:
        white_space["blueprints"] = build_strategic_wedges(
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("results", []),
        )["blueprints"]
    except Exception as exc:
        logger.exception("[white_space] strategic wedge FAILED")
        _record_node_failure("strategic_wedge", exc)

    logger.info("[white_space] COMPLETE")
    metrics.increment("node.white_space.success")
    return {
        **state,
        "whiteSpace": white_space,
    }


# --------------------------------------------------
# MILESTONE 3: STRATEGY AGENTS
# --------------------------------------------------

def swot_node(state: PipelineState) -> PipelineState:
    logger.info("[swot] START")
    if state.get("error"):
        return state
    if state.get("mode") == "quick":
        logger.info("[swot] Skipped - quick mode")
        return state
    try:
        value = analyze_swot(
            state["idea"],
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("whiteSpace"),
            state.get("results", []),
            allow_local=state.get("allowLocalLlm", False),
        )
    except NeedsDeepAnalysisError as exc:
        logger.warning("[swot] Needs deep analysis - short-circuiting pipeline")
        _record_node_failure("swot", exc)
        return {**state, "error": NEEDS_DEEP_ANALYSIS}
    except Exception as exc:
        logger.exception("[swot] FAILED")
        _record_node_failure("swot", exc)
        return {
            **state,
            "swot": None,
            "errors": {**state.get("errors", {}), "swot": _friendly_error_message(exc)},
        }
    logger.info("[swot] COMPLETE")
    metrics.increment("node.swot.success")
    return {**state, "swot": value}


def viability_score_node(state: PipelineState) -> PipelineState:
    """Deterministic - no LLM call, same "don't generate a fake score if
    upstream failed" rule opportunity_score_node follows: skipped entirely
    when marketOpportunity is None rather than scoring nothing as if it
    were real data. Still wrapped in the same try/except-per-node pattern
    every other node in this file uses - "no LLM call" made a crash here
    unlikely, not impossible, and this node used to be the one exception to
    that pattern, able to take the whole request down on any bug in
    viability_score.py despite everything upstream having already
    succeeded.
    """
    logger.info("[viability_score] START")
    if state.get("error"):
        return state
    if state.get("mode") == "quick":
        logger.info("[viability_score] Skipped - quick mode")
        return state

    market_opportunity = state.get("marketOpportunity")
    if market_opportunity is None:
        logger.warning("[viability_score] Skipped because marketOpportunity is None")
        return state

    try:
        value = calculate_market_viability(
            market_opportunity,
            state.get("swot"),
            state.get("competitors"),
            _source_recency(state.get("results", [])),
        )
    except Exception as exc:
        logger.exception("[viability_score] FAILED")
        _record_node_failure("viability_score", exc)
        return {
            **state,
            "marketViability": None,
            "errors": {**state.get("errors", {}), "marketViability": _friendly_error_message(exc)},
        }

    # Pillar 2: the 5-axis dynamics index lives on marketOpportunity (its
    # spec'd home), computed here rather than in market_agent.py because
    # two of its axes need swot/competitors, which only exist by now. Its
    # own try/except so a bug in the index can't take the headline score
    # (already computed above) down with it.
    try:
        index = calculate_viability_index(
            market_opportunity,
            state.get("swot"),
            state.get("competitors"),
            state.get("results", []),
            state.get("idea", ""),
        )
        market_opportunity = {**market_opportunity, "viabilityIndex": index}
    except Exception as exc:
        logger.exception("[viability_score] viability index FAILED")
        _record_node_failure("viability_index", exc)

    logger.info("[viability_score] COMPLETE - score=%s", value["score"])
    metrics.increment("node.viability_score.success")
    return {**state, "marketViability": value, "marketOpportunity": market_opportunity}


# mvp_node and gtm_node run as parallel branches off viability_score (see
# build_pipeline) - neither depends on the other's output. Each returns
# only the keys it actually owns instead of spreading the whole incoming
# state: spreading would make this node's stale copy of the other
# branch's key (e.g. mvp_node's copy of "gtm") race with that branch's
# real update to the same channel in the same step, which LangGraph
# rejects. The "error"/"errors" channels have merge reducers (above) so
# both branches can still write to them independently. LangGraph also
# rejects an update that touches zero keys, so each short-circuit below
# re-affirms this node's own key instead of returning the previous
# `state` unchanged.


def mvp_node(state: PipelineState) -> PipelineState:
    logger.info("[mvp] START")
    if state.get("error"):
        return {"mvp": state.get("mvp")}
    if state.get("mode") == "quick":
        logger.info("[mvp] Skipped - quick mode")
        return {"mvp": state.get("mvp")}
    try:
        value = analyze_mvp(
            state["idea"],
            state.get("problem", ""),
            state.get("swot"),
            state.get("marketOpportunity"),
            state.get("results", []),
            allow_local=state.get("allowLocalLlm", False),
        )
    except NeedsDeepAnalysisError as exc:
        logger.warning("[mvp] Needs deep analysis - short-circuiting pipeline")
        _record_node_failure("mvp", exc)
        return {"error": NEEDS_DEEP_ANALYSIS}
    except Exception as exc:
        logger.exception("[mvp] FAILED")
        _record_node_failure("mvp", exc)
        return {
            "mvp": None,
            "errors": {**state.get("errors", {}), "mvp": _friendly_error_message(exc)},
        }

    # Pillar 5B: stage-gated delivery roadmap, deterministic and built from
    # this node's own already-prioritized features (see
    # delivery_roadmap.py) - own try/except, same reasoning as
    # commercial_model above.
    try:
        value["deliveryRoadmap"] = build_delivery_roadmap(value)
    except Exception as exc:
        logger.exception("[mvp] delivery roadmap FAILED")
        _record_node_failure("delivery_roadmap", exc)

    logger.info("[mvp] COMPLETE")
    metrics.increment("node.mvp.success")
    return {"mvp": value}


def gtm_node(state: PipelineState) -> PipelineState:
    logger.info("[gtm] START")
    if state.get("error"):
        return {"gtm": state.get("gtm")}
    if state.get("mode") == "quick":
        logger.info("[gtm] Skipped - quick mode")
        return {"gtm": state.get("gtm")}
    try:
        value = analyze_gtm(
            state["idea"],
            state.get("targetCustomer", ""),
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("swot"),
            state.get("results", []),
            allow_local=state.get("allowLocalLlm", False),
        )
    except NeedsDeepAnalysisError as exc:
        logger.warning("[gtm] Needs deep analysis - short-circuiting pipeline")
        _record_node_failure("gtm", exc)
        return {"error": NEEDS_DEEP_ANALYSIS}
    except Exception as exc:
        logger.exception("[gtm] FAILED")
        _record_node_failure("gtm", exc)
        return {
            "gtm": None,
            "errors": {**state.get("errors", {}), "gtm": _friendly_error_message(exc)},
        }

    # Pillar 5A: unit economics + pricing tiers, deterministic (see
    # commercial_model.py) - its own try/except so a bug here can't take
    # down the LLM-backed GTM result already computed above.
    try:
        value["commercialModel"] = build_commercial_model(
            state["idea"],
            state.get("competitors"),
            value.get("channels"),
            state.get("swot"),
        )
    except Exception as exc:
        logger.exception("[gtm] commercial model FAILED")
        _record_node_failure("commercial_model", exc)

    logger.info("[gtm] COMPLETE")
    metrics.increment("node.gtm.success")
    return {"gtm": value}


# --------------------------------------------------
# TRACK B: CONTRADICTION DETECTOR
# --------------------------------------------------

def contradiction_detector_node(state: PipelineState) -> PipelineState:
    """Runs after SWOT/MVP/GTM/Score so every artifact it cross-checks is
    already in state. Same try/except-per-node pattern as the rest of this
    file: a failure here writes "contradictions": None and records the
    error, never erasing the sections already produced above it.
    """
    logger.info("[contradiction_detector] START")

    if state.get("error"):
        logger.warning("[contradiction_detector] Skipped because web search failed")
        return state
    if state.get("mode") == "quick":
        logger.info("[contradiction_detector] Skipped - quick mode")
        return state

    try:
        contradictions = detect_contradictions(
            state.get("marketOpportunity"),
            state.get("swot"),
            state.get("mvp"),
            state.get("gtm"),
        )
    except Exception as exc:
        logger.exception("[contradiction_detector] FAILED")
        return {
            **state,
            "contradictions": None,
            "errors": {**state.get("errors", {}), "contradictions": _friendly_error_message(exc)},
        }

    logger.info("[contradiction_detector] COMPLETE - %d flagged", len(contradictions))
    return {**state, "contradictions": contradictions}


# --------------------------------------------------
# TRACK C: VALIDATION EXPERIMENTS + FOUNDER ACTION PLAN
# --------------------------------------------------

def experiment_generator_node(state: PipelineState) -> PipelineState:
    """Runs after SWOT/MVP/Market so it has the risks/features/segments it
    needs. Same try/except-per-node pattern as the rest of this file, and
    kept as its own node (not merged with action_plan_node) so a failure in
    one never blocks the other.
    """
    logger.info("[experiment_generator] START")

    if state.get("error"):
        logger.warning("[experiment_generator] Skipped because web search failed")
        return state
    if state.get("mode") == "quick":
        logger.info("[experiment_generator] Skipped - quick mode")
        return state

    try:
        experiments = generate_experiments(
            state.get("swot"),
            state.get("marketOpportunity"),
            state.get("mvp"),
        )
    except Exception as exc:
        logger.exception("[experiment_generator] FAILED")
        return {
            **state,
            "experiments": None,
            "errors": {**state.get("errors", {}), "experiments": _friendly_error_message(exc)},
        }

    logger.info("[experiment_generator] COMPLETE - %d generated", len(experiments))
    return {**state, "experiments": experiments}


def action_plan_node(state: PipelineState) -> PipelineState:
    """Runs after GTM/MVP/SWOT so it has the channels/features/risks it
    needs. Same try/except-per-node pattern as the rest of this file.
    """
    logger.info("[action_plan] START")

    if state.get("error"):
        logger.warning("[action_plan] Skipped because web search failed")
        return state
    if state.get("mode") == "quick":
        logger.info("[action_plan] Skipped - quick mode")
        return state

    try:
        action_plan = generate_action_plan(
            state.get("gtm"),
            state.get("mvp"),
            state.get("swot"),
        )
    except Exception as exc:
        logger.exception("[action_plan] FAILED")
        return {
            **state,
            "actionPlan": None,
            "errors": {**state.get("errors", {}), "actionPlan": _friendly_error_message(exc)},
        }

    logger.info("[action_plan] COMPLETE")
    return {**state, "actionPlan": action_plan}


# --------------------------------------------------
# TRACK A: CONFIDENCE DASHBOARD
# --------------------------------------------------
#
# NOTE ON agent/confidence.py: that module's calculate_confidence() is dead
# code - only ever called from tests and scripts/smoke_test.py, never wired
# into this pipeline. The live /validate response has always come from
# confidence_node() above (a different contract: agreeingSources/
# totalSources/percentage/perAngle). This dashboard extension builds on the
# live node instead of the orphaned module, so there's exactly one
# confidence implementation reaching the frontend, not two silently
# diverging ones. confidence.py should be reconciled/removed separately.

_CLAIM_LIST_KEYS = ("strengths", "weaknesses", "opportunities", "threats")


def _collect_claims(state: PipelineState) -> list[dict]:
    """Gather every claim across the pipeline's evidence-backed sections
    that carries a "sourceIds" field: swot_agent.py's four claim lists and
    risks, mvp_agent.py's features, gtm_agent.py's channels, and
    market_agent.py's trends and segments (state["marketOpportunity"] -
    added once market's Track A sourceIds work landed). New items within
    these same sections are picked up automatically the moment they're
    shaped like {"sourceIds": [...]} - only an entirely new top-level
    section (a new dict key on state) needs a line added here.
    """
    claims: list[dict] = []

    swot = state.get("swot") or {}
    for key in _CLAIM_LIST_KEYS:
        for item in swot.get(key) or []:
            if isinstance(item, dict) and "sourceIds" in item:
                claims.append(item)
    for risk in swot.get("risks") or []:
        if isinstance(risk, dict) and "sourceIds" in risk:
            claims.append(risk)

    for feature in (state.get("mvp") or {}).get("features") or []:
        if isinstance(feature, dict) and "sourceIds" in feature:
            claims.append(feature)

    gtm = state.get("gtm") or {}
    for channel in gtm.get("channels") or []:
        if isinstance(channel, dict) and "sourceIds" in channel:
            claims.append(channel)

    market = state.get("marketOpportunity") or {}
    for trend in market.get("trends") or []:
        if isinstance(trend, dict) and "sourceIds" in trend:
            claims.append(trend)
    for segment in market.get("segments") or []:
        if isinstance(segment, dict) and "sourceIds" in segment:
            claims.append(segment)
    for tier in ("tam", "sam", "som"):
        value = market.get(tier)
        if isinstance(value, dict) and "sourceIds" in value:
            claims.append(value)
    if isinstance(market.get("marketSizeSourceIds"), list):
        claims.append({"text": market.get("marketSize", ""), "sourceIds": market["marketSizeSourceIds"]})

    return claims


def _source_relevance_by_id(results: list) -> dict[str, float]:
    """Map each "src-N" id back to its relevance score, using the exact same
    ordering compact_sources() used when the agents built their prompts -
    so a sourceId a claim cites resolves to the real score of the source it
    actually came from, not a guess.

    Uses market_agent.py's MAX_SOURCES_IN_CONTEXT (10), not
    compact_sources()'s own default limit (6), because market_agent.py
    shows the LLM up to 10 sources and sanitizes trend/segment sourceIds
    against that same wider window - a legitimate market citation of
    src-7..src-10 would otherwise have no relevance score here and get
    silently dropped from averageRelevance below.
    """
    sources = compact_sources(results, limit=MAX_SOURCES_IN_CONTEXT)
    lookup = {}
    for index, source in enumerate(sources):
        score = results[index].get("score") if index < len(results) else None
        if isinstance(score, (int, float)):
            lookup[source["sourceId"]] = score
    return lookup


def _parse_published_at(value) -> datetime | None:
    """Best-effort ISO-8601 parse of a source's publishedAt (see
    tools.py) - returns None on anything that doesn't parse rather than
    raising, since a malformed date from a provider is still "unknown",
    not a pipeline failure.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _source_recency(results: list) -> dict:
    """Real recency data where the underlying search provider actually
    exposes a publish date (Tavily sometimes does; Hacker News's Algolia
    API always does; DuckDuckGo's text search and Wikipedia's search API
    don't - see tools.py) - reports how many sources have a known date and
    their median age, rather than a blanket "unavailable" for the whole
    dashboard just because not every provider supports it.
    """
    total = len(results)
    ages_days = []
    for result in results:
        parsed = _parse_published_at(result.get("publishedAt"))
        if parsed is not None:
            ages_days.append((datetime.now(timezone.utc) - parsed).total_seconds() / 86400)

    if not ages_days:
        return {
            "sourcesWithKnownDate": 0,
            "totalSources": total,
            "medianAgeDays": None,
        }

    ages_days.sort()
    mid = len(ages_days) // 2
    median = ages_days[mid] if len(ages_days) % 2 else (ages_days[mid - 1] + ages_days[mid]) / 2

    return {
        "sourcesWithKnownDate": len(ages_days),
        "totalSources": total,
        "medianAgeDays": round(median, 1),
    }


def _confidence_dashboard(state: PipelineState) -> dict:
    """Extend the existing evidence-agreement indicator (confidence_node,
    computed early from raw search results) with the claim-level dashboard
    from docs/unique-features-plan.md §5.2: source coverage, average
    relevance, cross-source agreement, source recency, and a direct-
    evidence-vs-inferred ratio. Computed without another LLM call, same as
    the rest of this pipeline's deterministic post-processing steps.

    Also recomputes the headline agreeingSources/totalSources/percentage/
    label confidence_node first set - over cited sources instead of the
    full raw search pool. confidence_node necessarily runs before any
    claims exist, so it can only measure "how relevant is everything we
    retrieved" (30-50+ results blended across every search angle,
    including deliberately broad ones like industry news and customer
    demand that were never meant to individually match the idea tightly).
    That reads as a near-permanently low "Overall confidence" regardless of
    how well-evidenced the actual analysis is, since it's diluted by
    breadth the claims never even used. Once claims exist, "how relevant
    are the sources this analysis is actually built on" is both answerable
    and the more honest headline number - the same population sourceCoverage/
    averageRelevance/etc. below already use.
    """
    claims = _collect_claims(state)
    total_claims = len(claims)

    cited_ids: set[str] = set()
    claims_with_source = 0
    source_id_claim_count: dict[str, int] = {}
    for claim in claims:
        source_ids = claim.get("sourceIds") or []
        if source_ids:
            claims_with_source += 1
            cited_ids.update(source_ids)
        for sid in source_ids:
            source_id_claim_count[sid] = source_id_claim_count.get(sid, 0) + 1

    # "Cross-source agreement" = sources that back 2+ distinct findings.
    # The old metric (claims with 2+ sourceIds each) was structurally always
    # 0 because the strategy agents attach at most one sourceId per claim —
    # so it reported 0% on every run regardless of evidence quality.
    # Corroborated sources (one source cited by multiple findings) is the
    # meaningful signal: does the same evidence thread appear in more than
    # one part of the analysis?
    corroborated = sum(1 for cnt in source_id_claim_count.values() if cnt >= 2)
    total_unique_cited = len(source_id_claim_count)

    def _pct(numerator: int, denominator: int) -> int:
        return round((numerator / denominator) * 100) if denominator else 0

    relevance_by_id = _source_relevance_by_id(state.get("results", []))
    cited_scores = [relevance_by_id[sid] for sid in cited_ids if sid in relevance_by_id]
    average_relevance = round(sum(cited_scores) / len(cited_scores), 2) if cited_scores else None

    # Same >=0.5 "agrees" bar confidence_node used, just applied to the
    # cited population instead of the raw pool - so a source only counts
    # against the headline number if the analysis actually relied on it.
    agreeing_cited = sum(1 for score in cited_scores if score >= 0.5)
    total_cited = len(cited_scores)

    return {
        "agreeingSources": agreeing_cited,
        "totalSources": total_cited,
        "percentage": _pct(agreeing_cited, total_cited),
        "label": f"{agreeing_cited}/{total_cited} sources agree" if total_cited else "No cited sources yet",
        "sourceCoverage": {
            "claimsWithSource": claims_with_source,
            "totalClaims": total_claims,
            "percentage": _pct(claims_with_source, total_claims),
        },
        "averageRelevance": average_relevance,
        "crossSourceAgreement": {
            "corroboratedSources": corroborated,
            "totalUniqueSources": total_unique_cited,
            "percentage": _pct(corroborated, total_unique_cited),
        },
        "directEvidenceRatio": {
            "direct": claims_with_source,
            "inferred": total_claims - claims_with_source,
            "percentage": _pct(claims_with_source, total_claims),
        },
        "sourceRecency": _source_recency(state.get("results", [])),
    }


def confidence_dashboard_node(state: PipelineState) -> PipelineState:
    """Runs once every strategy agent has had a chance to produce
    sourceIds-bearing claims, merging the dashboard into the same
    "confidence" key confidence_node already populated. Additive for
    sourceCoverage/averageRelevance/crossSourceAgreement/
    directEvidenceRatio/sourceRecency (all new here) and leaves
    confidence_node's own perAngle breakdown untouched - but this
    intentionally overwrites confidence_node's headline agreeingSources/
    totalSources/percentage/label with the cited-sources recomputation
    above, which is why this node always runs after confidence_node in the
    graph rather than the two being independent.
    """
    logger.info("[confidence_dashboard] START")

    if state.get("error"):
        logger.warning("[confidence_dashboard] Skipped because web search failed")
        return state

    try:
        dashboard = _confidence_dashboard(state)
    except Exception:
        logger.exception("[confidence_dashboard] FAILED")
        return state

    confidence = {**(state.get("confidence") or {}), **dashboard}
    logger.info(
        "[confidence_dashboard] COMPLETE - overall %s%%, source coverage %s%%",
        dashboard["percentage"],
        dashboard["sourceCoverage"]["percentage"],
    )
    return {**state, "confidence": confidence}


def verdict_node(state: PipelineState) -> PipelineState:
    """Final go / no-go verdict (see verdict.py). Runs last so it can read
    viability, SWOT risks, assumptions and the confidence dashboard. Runs
    in quick mode too, falling back to the Opportunity Score, since a
    headline answer is still useful without the strategy nodes."""
    if state.get("error"):
        return state
    try:
        value = build_verdict(
            state.get("marketOpportunity"),
            market_viability=state.get("marketViability"),
            swot=state.get("swot"),
            assumptions=state.get("assumptions"),
            confidence=state.get("confidence"),
        )
    except Exception:
        logger.exception("[verdict] FAILED")
        return state
    return {**state, "verdict": value}


# --------------------------------------------------
# NOVEL FEATURE: ASSUMPTION TRACKER
# --------------------------------------------------

def assumption_tracker_node(state: PipelineState) -> PipelineState:
    """Surfaces the 3-5 riskiest hidden assumptions underlying the analysis,
    ranked by uncertainty, each with a concrete how-to-validate step.
    Runs after SWOT/MVP so it has the richest context to reason from.
    """
    logger.info("[assumption_tracker] START")
    if state.get("error"):
        logger.warning("[assumption_tracker] Skipped because web search failed")
        return state
    if state.get("mode") == "quick":
        logger.info("[assumption_tracker] Skipped - quick mode")
        return state
    try:
        value = analyze_assumptions(
            state["idea"],
            state.get("targetCustomer", ""),
            state.get("problem", ""),
            state.get("swot"),
            state.get("marketOpportunity"),
            state.get("mvp"),
            state.get("results", []),
            allow_local=state.get("allowLocalLlm", False),
        )
    except NeedsDeepAnalysisError as exc:
        logger.warning("[assumption_tracker] Needs deep analysis - short-circuiting pipeline")
        _record_node_failure("assumption_tracker", exc)
        return {**state, "error": NEEDS_DEEP_ANALYSIS}
    except Exception as exc:
        logger.exception("[assumption_tracker] FAILED")
        _record_node_failure("assumption_tracker", exc)
        return {
            **state,
            "assumptions": None,
            "errors": {**state.get("errors", {}), "assumptions": _friendly_error_message(exc)},
        }
    logger.info("[assumption_tracker] COMPLETE")
    metrics.increment("node.assumption_tracker.success")
    return {**state, "assumptions": value}


# --------------------------------------------------
# NOVEL FEATURE: REVENUE MODEL SUGGESTER
# --------------------------------------------------

def revenue_models_node(state: PipelineState) -> PipelineState:
    """Suggests 2-3 revenue models matched to the specific market dynamics
    and customer segments already evidenced in the pipeline.
    Runs after market_opportunity and competitor_discovery.
    """
    logger.info("[revenue_models] START")
    if state.get("error"):
        logger.warning("[revenue_models] Skipped because web search failed")
        return state
    if state.get("mode") == "quick":
        logger.info("[revenue_models] Skipped - quick mode")
        return state
    try:
        value = analyze_revenue_models(
            state["idea"],
            state.get("targetCustomer", ""),
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("results", []),
            allow_local=state.get("allowLocalLlm", False),
        )
    except NeedsDeepAnalysisError as exc:
        logger.warning("[revenue_models] Needs deep analysis - short-circuiting pipeline")
        _record_node_failure("revenue_models", exc)
        return {**state, "error": NEEDS_DEEP_ANALYSIS}
    except Exception as exc:
        logger.exception("[revenue_models] FAILED")
        _record_node_failure("revenue_models", exc)
        return {
            **state,
            "revenueModels": None,
            "errors": {**state.get("errors", {}), "revenueModels": _friendly_error_message(exc)},
        }
    logger.info("[revenue_models] COMPLETE")
    metrics.increment("node.revenue_models.success")
    return {**state, "revenueModels": value}


# --------------------------------------------------
# BUILD LANGGRAPH PIPELINE
# --------------------------------------------------

def _timed(node_name: str, fn):
    """Wrap a node so its wall-clock time is logged without touching every
    node function's own body - this is the per-node latency data Track F's
    optimization pass needs and previously had no way to measure (only
    START/COMPLETE markers existed, with no duration between them).

    Also records a durable "node_latency" event (agent/events.py) so GET
    /admin/platform-metrics can report per-node averages and trends, not
    just whatever's in this process's own log stream.
    """

    def wrapper(state: PipelineState) -> PipelineState:
        start = time.time()
        result = fn(state)
        elapsed_seconds = time.time() - start
        elapsed_ms = round(elapsed_seconds * 1000)
        logger.info("[%s] elapsed_ms=%d", node_name, elapsed_ms)
        events.record("node_latency", node=node_name, detail={"seconds": round(elapsed_seconds, 3)})
        return result

    return wrapper


def build_pipeline():
    graph = StateGraph(PipelineState)

    # --------------------------------------------------
    # NODES
    # --------------------------------------------------

    graph.add_node(
        "web_search",
        _timed("web_search", web_search_node),
    )

    # Sashi: Cross-source confidence
    graph.add_node(
        "confidence_indicator",
        _timed("confidence_indicator", confidence_node),
    )

    graph.add_node(
        "market_opportunity",
        _timed("market_opportunity", market_opportunity_node),
    )

    graph.add_node(
        "competitor_discovery",
        _timed("competitor_discovery", competitor_discovery_node),
    )

    # Sashi: Opportunity Score
    graph.add_node(
        "opportunity_score",
        _timed("opportunity_score", opportunity_score_node),
    )

    graph.add_node(
        "white_space",
        _timed("white_space", white_space_node),
    )

    graph.add_node("swot_analysis", _timed("swot_analysis", swot_node))
    graph.add_node("viability_score", _timed("viability_score", viability_score_node))
    graph.add_node("mvp_recommendation", _timed("mvp_recommendation", mvp_node))
    graph.add_node("gtm_strategy", _timed("gtm_strategy", gtm_node))

    # Track B: contradiction detector - runs after SWOT/MVP/GTM/Score so
    # every artifact it cross-checks is already in state.
    graph.add_node(
        "contradiction_detector",
        _timed("contradiction_detector", contradiction_detector_node),
    )

    # Track C: validation experiments + founder action plan - each its own
    # node (not merged with contradiction_detector or each other) so a
    # failure in one never blocks the others, same isolation the rest of
    # this file already gives every section.
    graph.add_node(
        "experiment_generator",
        _timed("experiment_generator", experiment_generator_node),
    )
    graph.add_node("action_plan", _timed("action_plan", action_plan_node))

    # Novel features: assumption tracker + revenue model suggester
    graph.add_node("assumption_tracker", _timed("assumption_tracker", assumption_tracker_node))
    graph.add_node("revenue_models", _timed("revenue_models", revenue_models_node))

    # Track A: confidence dashboard (source coverage, cross-source
    # agreement, direct-evidence ratio) - runs last so it can see every
    # strategy agent's sourceIds-bearing claims.
    graph.add_node("confidence_dashboard", _timed("confidence_dashboard", confidence_dashboard_node))
    graph.add_node("compute_verdict", _timed("verdict", verdict_node))

    # --------------------------------------------------
    # PIPELINE FLOW
    # --------------------------------------------------

    # START
    graph.add_edge(
        START,
        "web_search",
    )

    # Web Search
    #        ↓
    # Confidence
    graph.add_edge(
        "web_search",
        "confidence_indicator",
    )

    # Confidence
    #        ↓
    # Market Opportunity
    graph.add_edge(
        "confidence_indicator",
        "market_opportunity",
    )

    # Market Opportunity
    #        ↓
    # Competitor Discovery
    graph.add_edge(
        "market_opportunity",
        "competitor_discovery",
    )

    # Competitor Discovery
    #        ↓
    # Opportunity Score
    graph.add_edge(
        "competitor_discovery",
        "opportunity_score",
    )

    # Opportunity Score
    #        ↓
    # White-space Analysis
    graph.add_edge(
        "opportunity_score",
        "white_space",
    )

    graph.add_edge("white_space", "swot_analysis")
    graph.add_edge("swot_analysis", "viability_score")

    # mvp_recommendation and gtm_strategy each only depend on swot/
    # marketOpportunity/competitors (already computed by this point), not
    # on each other, so they fan out from viability_score and run
    # concurrently instead of sequentially - removing one full LLM
    # round-trip from every request's critical path. contradiction_detector
    # fans back in and waits for both.
    graph.add_edge("viability_score", "mvp_recommendation")
    graph.add_edge("viability_score", "gtm_strategy")
    graph.add_edge("mvp_recommendation", "contradiction_detector")
    graph.add_edge("gtm_strategy", "contradiction_detector")
    graph.add_edge("contradiction_detector", "experiment_generator")
    graph.add_edge("experiment_generator", "action_plan")
    graph.add_edge("action_plan", "assumption_tracker")
    graph.add_edge("assumption_tracker", "revenue_models")
    graph.add_edge("revenue_models", "confidence_dashboard")
    graph.add_edge("confidence_dashboard", "compute_verdict")
    graph.add_edge("compute_verdict", END)

    return graph.compile()


# --------------------------------------------------
# FINAL PIPELINE
# --------------------------------------------------

pipeline = build_pipeline()
