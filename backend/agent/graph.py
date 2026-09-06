import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .competitor_agent import analyze_competitors
from .market_agent import analyze_market_opportunity
from .opportunity_score import calculate_opportunity_score

logger = logging.getLogger(__name__)


def _friendly_error_message(exc: Exception) -> str:
    """The raw exception (a multi-line litellm/Groq stack trace, JSON blob and
    all) is exactly what you want in server logs and useless/alarming as
    user-facing copy. logger.exception already captured the full detail above
    this call - this is only what reaches errors.<node> and the frontend.
    """
    text = str(exc)
    if "RateLimitError" in text or "rate_limit" in text:
        return "This analysis hit a temporary usage limit. Please try again in a moment."
    return "This analysis couldn't be completed for this request. Please try again."


def _build_summary(idea: str, results: list) -> str:
    """Template-built from the search results directly - no LLM call.

    This used to ask an LLM to paraphrase the same results into 2-3
    sentences, but that call was rejected by the reasoning-leak quality gate
    often enough that this exact template was already the de facto summary
    most of the time. Since it was already doing the real work, making it
    the only path cuts one of the three LLM calls per request (a real ~33%
    reduction in Groq usage) with zero effect on Market Opportunity/
    Competitor Discovery's independent failure handling - it's a separate
    node from both.
    """
    if not results:
        return f'No market data found yet for "{idea}".'

    angles = sorted({r.get("angle", "") for r in results} - {""})
    coverage = ", ".join(angles) if angles else "the web"

    return (
        f'Found {len(results)} relevant sources for "{idea}", covering {coverage}. '
        "See the results below for details."
    )


class PipelineState(TypedDict, total=False):
    idea: str
    targetCustomer: str
    problem: str
    summary: str
    results: list
    marketOpportunity: dict
    competitors: dict
    error: str
    errors: dict


def web_search_node(state: PipelineState) -> PipelineState:
    """M1 node: collects real results and builds a summary directly from
    them - no LLM call (see _build_summary)."""

    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")

    try:
        results = retrieval.collect(idea, target_customer, problem)
    except Exception as exc:
        return {**state, "error": str(exc)}

    return {
        **state,
        "summary": _build_summary(idea, results),
        "results": results,
    }


def market_opportunity_node(state: PipelineState) -> PipelineState:
    """M2 node: Market Opportunity & Customer Segmentation Analysis."""

    logger.info("[market_opportunity] START")

    if state.get("error"):
        logger.warning("[market_opportunity] Skipped because web search failed")
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

def competitor_discovery_node(state: PipelineState) -> PipelineState:
    """M2 node: Competitor Discovery & Comparison Agent."""

    logger.info("[competitor_discovery] START")

    if state.get("error"):
        logger.warning("[competitor_discovery] Skipped because web search failed")
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


# -------------------------------
# MILESTONE 2: OPPORTUNITY SCORE
# -------------------------------

def opportunity_score_node(state: PipelineState) -> PipelineState:
    """Calculate the Opportunity Score using market and competitor data."""

    if state.get("error"):
        return state

    market_opportunity = state.get("marketOpportunity")
    competitors = state.get("competitors")
    results = state.get("results", [])

    if market_opportunity is None:
        # The market_opportunity node itself failed - errors.marketOpportunity
        # already reflects that, and there's no dict left to attach a score to.
        # Don't fabricate one; the frontend already shows this section as
        # unavailable.
        return state

    try:
        score = calculate_opportunity_score(
            market_opportunity,
            competitors,
            results,
        )
        market_opportunity["opportunityScore"] = score
    except Exception:
        logger.exception("Opportunity score calculation failed")
        market_opportunity["opportunityScore"] = 0

    return {
        **state,
        "marketOpportunity": market_opportunity,
    }


def build_pipeline():
    graph = StateGraph(PipelineState)

    # Existing nodes
    graph.add_node("web_search", web_search_node)
    graph.add_node("market_opportunity", market_opportunity_node)
    graph.add_node("competitor_discovery", competitor_discovery_node)

    # Sashi's Milestone 2 feature
    graph.add_node("opportunity_score", opportunity_score_node)

    # Pipeline flow
    graph.add_edge(START, "web_search")
    graph.add_edge("web_search", "market_opportunity")
    graph.add_edge("market_opportunity", "competitor_discovery")

    # Calculate score after both analyses are available
    graph.add_edge("competitor_discovery", "opportunity_score")
    graph.add_edge("opportunity_score", END)

    return graph.compile()


pipeline = build_pipeline()
