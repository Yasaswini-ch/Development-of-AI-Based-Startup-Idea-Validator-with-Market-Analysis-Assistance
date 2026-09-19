import logging
import time
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .competitor_agent import analyze_competitors
from .gtm_agent import analyze_gtm
from .market_agent import MAX_SOURCES_IN_CONTEXT, analyze_market_opportunity
from .mvp_agent import analyze_mvp
from .opportunity_score import calculate_opportunity_score
from .structured_output import compact_sources
from .swot_agent import analyze_swot
from .white_space import analyze_white_space

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

    # Evidence-backed opportunity gaps
    whiteSpace: dict

    # Milestone 3 strategy artifacts
    swot: dict
    mvp: dict
    gtm: dict

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
        errors = {
            **state.get("errors", {}),
            "whiteSpace": _friendly_error_message(exc),
        }
        return {
            **state,
            "whiteSpace": None,
            "errors": errors,
        }

    logger.info("[white_space] COMPLETE")
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
    try:
        value = analyze_swot(
            state["idea"],
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("whiteSpace"),
            state.get("results", []),
        )
    except Exception as exc:
        logger.exception("[swot] FAILED")
        return {
            **state,
            "swot": None,
            "errors": {**state.get("errors", {}), "swot": _friendly_error_message(exc)},
        }
    logger.info("[swot] COMPLETE")
    return {**state, "swot": value}


def mvp_node(state: PipelineState) -> PipelineState:
    logger.info("[mvp] START")
    if state.get("error"):
        return state
    try:
        value = analyze_mvp(
            state["idea"],
            state.get("problem", ""),
            state.get("swot"),
            state.get("marketOpportunity"),
            state.get("results", []),
        )
    except Exception as exc:
        logger.exception("[mvp] FAILED")
        return {
            **state,
            "mvp": None,
            "errors": {**state.get("errors", {}), "mvp": _friendly_error_message(exc)},
        }
    logger.info("[mvp] COMPLETE")
    return {**state, "mvp": value}


def gtm_node(state: PipelineState) -> PipelineState:
    logger.info("[gtm] START")
    if state.get("error"):
        return state
    try:
        value = analyze_gtm(
            state["idea"],
            state.get("targetCustomer", ""),
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("swot"),
            state.get("results", []),
        )
    except Exception as exc:
        logger.exception("[gtm] FAILED")
        return {
            **state,
            "gtm": None,
            "errors": {**state.get("errors", {}), "gtm": _friendly_error_message(exc)},
        }
    logger.info("[gtm] COMPLETE")
    return {**state, "gtm": value}


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
    """
    claims = _collect_claims(state)
    total_claims = len(claims)

    cited_ids: set[str] = set()
    claims_with_source = 0
    claims_with_multiple = 0
    for claim in claims:
        source_ids = claim.get("sourceIds") or []
        if source_ids:
            claims_with_source += 1
            cited_ids.update(source_ids)
        if len(source_ids) >= 2:
            claims_with_multiple += 1

    def _pct(numerator: int, denominator: int) -> int:
        return round((numerator / denominator) * 100) if denominator else 0

    relevance_by_id = _source_relevance_by_id(state.get("results", []))
    cited_scores = [relevance_by_id[sid] for sid in cited_ids if sid in relevance_by_id]
    average_relevance = round(sum(cited_scores) / len(cited_scores), 2) if cited_scores else None

    return {
        "sourceCoverage": {
            "claimsWithSource": claims_with_source,
            "totalClaims": total_claims,
            "percentage": _pct(claims_with_source, total_claims),
        },
        "averageRelevance": average_relevance,
        "crossSourceAgreement": {
            "claimsWithMultipleSources": claims_with_multiple,
            "totalClaims": total_claims,
            "percentage": _pct(claims_with_multiple, total_claims),
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
    "confidence" key confidence_node already populated - additive, never
    replacing the existing agreeingSources/percentage/perAngle fields the
    frontend may already read.
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
        "[confidence_dashboard] COMPLETE - source coverage %s%%",
        dashboard["sourceCoverage"]["percentage"],
    )
    return {**state, "confidence": confidence}


# --------------------------------------------------
# BUILD LANGGRAPH PIPELINE
# --------------------------------------------------

def _timed(node_name: str, fn):
    """Wrap a node so its wall-clock time is logged without touching every
    node function's own body - this is the per-node latency data Track F's
    optimization pass needs and previously had no way to measure (only
    START/COMPLETE markers existed, with no duration between them).
    """

    def wrapper(state: PipelineState) -> PipelineState:
        start = time.time()
        result = fn(state)
        elapsed_ms = round((time.time() - start) * 1000)
        logger.info("[%s] elapsed_ms=%d", node_name, elapsed_ms)
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
    graph.add_node("mvp_recommendation", _timed("mvp_recommendation", mvp_node))
    graph.add_node("gtm_strategy", _timed("gtm_strategy", gtm_node))

    # Track A: confidence dashboard (source coverage, cross-source
    # agreement, direct-evidence ratio) - runs last so it can see every
    # strategy agent's sourceIds-bearing claims.
    graph.add_node("confidence_dashboard", _timed("confidence_dashboard", confidence_dashboard_node))

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
    graph.add_edge("swot_analysis", "mvp_recommendation")
    graph.add_edge("mvp_recommendation", "gtm_strategy")
    graph.add_edge("gtm_strategy", "confidence_dashboard")
    graph.add_edge("confidence_dashboard", END)

    return graph.compile()


# --------------------------------------------------
# FINAL PIPELINE
# --------------------------------------------------

pipeline = build_pipeline()
