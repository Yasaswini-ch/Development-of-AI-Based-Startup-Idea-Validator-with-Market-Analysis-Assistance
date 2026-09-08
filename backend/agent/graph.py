import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .competitor_agent import analyze_competitors
from .market_agent import analyze_market_opportunity
from .opportunity_score import calculate_opportunity_score

logger = logging.getLogger(__name__)


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

def _friendly_error_message(exc: Exception) -> str:
    """Convert internal exceptions into user-friendly error messages."""
    text = str(exc)

    if "RateLimitError" in text or "rate_limit" in text:
        return "This analysis hit a temporary usage limit. Please try again in a moment."

    return "This analysis couldn't be completed for this request. Please try again."


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

class PipelineState(TypedDict, total=False):
    idea: str
    targetCustomer: str
    problem: str

    summary: str
    results: list

    # Cross-source confidence
    confidence: dict

    # Market analysis
    marketOpportunity: dict

    # Competitor analysis
    competitors: dict

    # Errors
    error: str
    errors: dict


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

        return {
            **state,
            "error": str(exc),
        }

    logger.info(
        "[web_search] COMPLETE - %d results",
        len(results),
    )

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
        )

        logger.info("[market_opportunity] COMPLETE")

        return {
            **state,
            "marketOpportunity": market_opportunity,
        }

    except Exception as exc:
        logger.exception("[market_opportunity] FAILED")

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
        competitors = analyze_competitors(
            idea,
            target_customer,
            problem,
            results,
        )

        logger.info("[competitor_discovery] COMPLETE")

        return {
            **state,
            "competitors": competitors,
        }

    except Exception as exc:
        logger.exception("[competitor_discovery] FAILED")

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

    except Exception:
        logger.exception("[opportunity_score] FAILED")

        # Safe fallback
        market_opportunity["opportunityScore"] = 0

    return {
        **state,
        "marketOpportunity": market_opportunity,
    }


# --------------------------------------------------
# BUILD LANGGRAPH PIPELINE
# --------------------------------------------------

def build_pipeline():
    graph = StateGraph(PipelineState)

    # --------------------------------------------------
    # NODES
    # --------------------------------------------------

    graph.add_node(
        "web_search",
        web_search_node,
    )

    # Sashi: Cross-source confidence
    graph.add_node(
        "confidence",
        confidence_node,
    )

    graph.add_node(
        "market_opportunity",
        market_opportunity_node,
    )

    graph.add_node(
        "competitor_discovery",
        competitor_discovery_node,
    )

    # Sashi: Opportunity Score
    graph.add_node(
        "opportunity_score",
        opportunity_score_node,
    )

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
        "confidence",
    )

    # Confidence
    #        ↓
    # Market Opportunity
    graph.add_edge(
        "confidence",
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
    # END
    graph.add_edge(
        "opportunity_score",
        END,
    )

    return graph.compile()


# --------------------------------------------------
# FINAL PIPELINE
# --------------------------------------------------

pipeline = build_pipeline()