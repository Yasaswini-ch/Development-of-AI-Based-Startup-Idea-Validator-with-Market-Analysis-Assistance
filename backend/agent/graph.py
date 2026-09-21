import logging
import time
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .competitor_agent import analyze_competitors
from .contradiction_detector import detect_contradictions
from .gtm_agent import analyze_gtm
from .market_agent import MAX_SOURCES_IN_CONTEXT, analyze_market_opportunity
from .mvp_agent import analyze_mvp
from .opportunity_score import calculate_opportunity_score
from .structured_output import compact_sources
from .swot_agent import analyze_swot
from .white_space import analyze_white_space

logger = logging.getLogger(__name__)


# ============================================================
# ERROR HANDLING
# ============================================================

def _friendly_error_message(exc: Exception) -> str:
    """Convert internal exceptions into user-friendly error messages."""
    text = str(exc)

    if "RateLimitError" in text or "rate_limit" in text:
        return (
            "This analysis hit a temporary usage limit. "
            "Please try again in a moment."
        )

    return (
        "This analysis couldn't be completed for this request. "
        "Please try again."
    )


# ============================================================
# SUMMARY
# ============================================================

def _build_summary(idea: str, results: list) -> str:
    """Build a summary directly from web-search results."""

    if not results:
        return f'No market data found yet for "{idea}".'

    angles = sorted(
        {
            r.get("angle", "")
            for r in results
            if isinstance(r, dict)
        }
        - {""}
    )

    coverage = ", ".join(angles) if angles else "the web"

    return (
        f'Found {len(results)} relevant sources for "{idea}", '
        f"covering {coverage}. See the results below for details."
    )


# ============================================================
# PIPELINE STATE
# ============================================================

class PipelineState(TypedDict, total=False):
    # User input
    idea: str
    targetCustomer: str
    problem: str
    industry: str
    location: str
    budget: str
    stage: str

    # Search
    summary: str
    results: list

    # Cross-source confidence
    confidence: dict

    # Market analysis
    marketOpportunity: dict

    # Competitor analysis
    competitors: dict

    # White-space analysis
    whiteSpace: dict

    # Strategy artifacts
    swot: dict
    mvp: dict
    gtm: dict

    # Contradictions
    contradictions: list

    # Errors
    error: str
    errors: dict


# ============================================================
# MILESTONE 1: WEB SEARCH
# ============================================================

def web_search_node(state: PipelineState) -> PipelineState:
    """
    Collect real web-search results.

    IMPORTANT:
    industry and location are explicitly forwarded to retrieval.collect()
    so retrieval can create idea-specific queries.
    """

    logger.info("[web_search] START")

    idea = state.get("idea", "")
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")
    industry = state.get("industry", "")
    location = state.get("location", "")

    logger.info(
        "[web_search] INPUT | idea=%s | targetCustomer=%s | "
        "problem=%s | industry=%s | location=%s",
        idea[:150],
        target_customer,
        problem[:150],
        industry,
        location,
    )

    try:
        # ----------------------------------------------------
        # IMPORTANT FIX
        # Pass ALL relevant fields to retrieval.
        # ----------------------------------------------------
        results = retrieval.collect(
            idea=idea,
            target_customer=target_customer,
            problem=problem,
            industry=industry,
            location=location,
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

    # --------------------------------------------------------
    # LOG ACTUAL SEARCH QUERIES
    # --------------------------------------------------------
    #
    # This is useful for debugging.
    # If old queries such as:
    #
    # "platform recommendations market"
    #
    # appear here, then another retrieval function is being used.
    #
    # --------------------------------------------------------

    for index, result in enumerate(results, start=1):

        if not isinstance(result, dict):
            continue

        logger.info(
            "[web_search] RESULT #%d | angle=%s | query=%s | "
            "score=%s | title=%s",
            index,
            result.get("angle"),
            result.get("query"),
            result.get("score"),
            result.get("title"),
        )

    return {
        **state,
        "summary": _build_summary(idea, results),
        "results": results,
    }


# ============================================================
# CROSS-SOURCE CONFIDENCE
# ============================================================

def confidence_node(state: PipelineState) -> PipelineState:
    """
    Calculate cross-source confidence from relevance scores.
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

    # --------------------------------------------------------
    # Group by angle
    # --------------------------------------------------------

    angles = {}

    for result in results:

        if not isinstance(result, dict):
            continue

        angle = result.get("angle", "Sources")

        if angle not in angles:
            angles[angle] = []

        angles[angle].append(result)

    # --------------------------------------------------------
    # Per-angle confidence
    # --------------------------------------------------------

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
            "label": (
                f"{agreeing_sources}/"
                f"{scored_total} sources agree"
            ),
        }

    # --------------------------------------------------------
    # Overall confidence
    # --------------------------------------------------------

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
        "label": (
            f"{agreeing_total}/"
            f"{total_scored} sources agree"
        ),
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


# ============================================================
# MARKET OPPORTUNITY
# ============================================================

def market_opportunity_node(state: PipelineState) -> PipelineState:
    """Market Opportunity & Customer Segmentation Analysis."""

    logger.info("[market_opportunity] START")

    if state.get("error"):
        logger.warning(
            "[market_opportunity] Skipped because web search failed"
        )
        return state

    idea = state.get("idea", "")
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

        logger.info(
            "[market_opportunity] COMPLETE"
        )

        return {
            **state,
            "marketOpportunity": market_opportunity,
        }

    except Exception as exc:

        logger.exception(
            "[market_opportunity] FAILED"
        )

        errors = {
            **state.get("errors", {}),
            "marketOpportunity": _friendly_error_message(exc),
        }

        return {
            **state,
            "marketOpportunity": None,
            "errors": errors,
        }


# ============================================================
# COMPETITOR DISCOVERY
# ============================================================

def competitor_discovery_node(state: PipelineState) -> PipelineState:
    """Competitor Discovery & Comparison Agent."""

    logger.info("[competitor_discovery] START")

    if state.get("error"):
        logger.warning(
            "[competitor_discovery] Skipped because web search failed"
        )
        return state

    idea = state.get("idea", "")
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

        logger.info(
            "[competitor_discovery] COMPLETE"
        )

        return {
            **state,
            "competitors": competitors,
        }

    except Exception as exc:

        logger.exception(
            "[competitor_discovery] FAILED"
        )

        errors = {
            **state.get("errors", {}),
            "competitors": _friendly_error_message(exc),
        }

        return {
            **state,
            "competitors": None,
            "errors": errors,
        }


# ============================================================
# OPPORTUNITY SCORE
# ============================================================

def opportunity_score_node(state: PipelineState) -> PipelineState:
    """
    Calculate Opportunity Score using:

    - Market Size
    - Market Growth / Trends
    - Competitor Density
    """

    logger.info("[opportunity_score] START")

    if state.get("error"):
        logger.warning(
            "[opportunity_score] Skipped because web search failed"
        )
        return state

    market_opportunity = state.get(
        "marketOpportunity"
    )

    competitors = state.get(
        "competitors"
    )

    results = state.get(
        "results",
        []
    )

    if market_opportunity is None:

        logger.warning(
            "[opportunity_score] Skipped because "
            "marketOpportunity is None"
        )

        return state

    try:

        score = calculate_opportunity_score(
            market_opportunity,
            competitors,
            results,
        )

        market_opportunity["opportunityScore"] = score

        logger.info(
            "[opportunity_score] COMPLETE - score=%s",
            score,
        )

    except Exception:

        logger.exception(
            "[opportunity_score] FAILED"
        )

        market_opportunity["opportunityScore"] = 0

    return {
        **state,
        "marketOpportunity": market_opportunity,
    }


# ============================================================
# WHITE SPACE
# ============================================================

def white_space_node(state: PipelineState) -> PipelineState:
    """
    Identify opportunity gaps using existing pipeline artifacts.
    """

    logger.info("[white_space] START")

    if state.get("error"):
        logger.warning(
            "[white_space] Skipped because web search failed"
        )
        return state

    try:

        white_space = analyze_white_space(
            state.get("marketOpportunity"),
            state.get("competitors"),
            state.get("results", []),
        )

    except Exception as exc:

        logger.exception(
            "[white_space] FAILED"
        )

        errors = {
            **state.get("errors", {}),
            "whiteSpace": _friendly_error_message(exc),
        }

        return {
            **state,
            "whiteSpace": None,
            "errors": errors,
        }

    logger.info(
        "[white_space] COMPLETE"
    )

    return {
        **state,
        "whiteSpace": white_space,
    }


# ============================================================
# SWOT
# ============================================================

def swot_node(state: PipelineState) -> PipelineState:

    logger.info("[swot] START")

    if state.get("error"):
        return state

    try:

        value = analyze_swot(
            state.get("idea", ""),
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
            "errors": {
                **state.get("errors", {}),
                "swot": _friendly_error_message(exc),
            },
        }

    logger.info("[swot] COMPLETE")

    return {
        **state,
        "swot": value,
    }


# ============================================================
# MVP
# ============================================================

def mvp_node(state: PipelineState) -> PipelineState:

    logger.info("[mvp] START")

    if state.get("error"):
        return state

    try:

        value = analyze_mvp(
            state.get("idea", ""),
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
            "errors": {
                **state.get("errors", {}),
                "mvp": _friendly_error_message(exc),
            },
        }

    logger.info("[mvp] COMPLETE")

    return {
        **state,
        "mvp": value,
    }


# ============================================================
# GTM
# ============================================================

def gtm_node(state: PipelineState) -> PipelineState:

    logger.info("[gtm] START")

    if state.get("error"):
        return state

    try:

        value = analyze_gtm(
            state.get("idea", ""),
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
            "errors": {
                **state.get("errors", {}),
                "gtm": _friendly_error_message(exc),
            },
        }

    logger.info("[gtm] COMPLETE")

    return {
        **state,
        "gtm": value,
    }


# ============================================================
# CONTRADICTION DETECTOR
# ============================================================

def contradiction_detector_node(
    state: PipelineState,
) -> PipelineState:
    """
    Cross-check market, SWOT, MVP and GTM artifacts.
    """

    logger.info(
        "[contradiction_detector] START"
    )

    if state.get("error"):

        logger.warning(
            "[contradiction_detector] "
            "Skipped because web search failed"
        )

        return state

    try:

        contradictions = detect_contradictions(
            state.get("marketOpportunity"),
            state.get("swot"),
            state.get("mvp"),
            state.get("gtm"),
        )

    except Exception as exc:

        logger.exception(
            "[contradiction_detector] FAILED"
        )

        return {
            **state,
            "contradictions": None,
            "errors": {
                **state.get("errors", {}),
                "contradictions": (
                    _friendly_error_message(exc)
                ),
            },
        }

    logger.info(
        "[contradiction_detector] COMPLETE - %d flagged",
        len(contradictions),
    )

    return {
        **state,
        "contradictions": contradictions,
    }


# ============================================================
# CONFIDENCE DASHBOARD
# ============================================================

_CLAIM_LIST_KEYS = (
    "strengths",
    "weaknesses",
    "opportunities",
    "threats",
)


def _collect_claims(
    state: PipelineState,
) -> list[dict]:
    """
    Collect evidence-backed claims containing sourceIds.
    """

    claims: list[dict] = []

    # --------------------------------------------------------
    # SWOT
    # --------------------------------------------------------

    swot = state.get("swot") or {}

    for key in _CLAIM_LIST_KEYS:

        for item in swot.get(key) or []:

            if (
                isinstance(item, dict)
                and "sourceIds" in item
            ):
                claims.append(item)

    for risk in swot.get("risks") or []:

        if (
            isinstance(risk, dict)
            and "sourceIds" in risk
        ):
            claims.append(risk)

    # --------------------------------------------------------
    # MVP
    # --------------------------------------------------------

    mvp = state.get("mvp") or {}

    for feature in mvp.get("features") or []:

        if (
            isinstance(feature, dict)
            and "sourceIds" in feature
        ):
            claims.append(feature)

    # --------------------------------------------------------
    # GTM
    # --------------------------------------------------------

    gtm = state.get("gtm") or {}

    for channel in gtm.get("channels") or []:

        if (
            isinstance(channel, dict)
            and "sourceIds" in channel
        ):
            claims.append(channel)

    # --------------------------------------------------------
    # MARKET
    # --------------------------------------------------------

    market = state.get(
        "marketOpportunity"
    ) or {}

    for trend in market.get("trends") or []:

        if (
            isinstance(trend, dict)
            and "sourceIds" in trend
        ):
            claims.append(trend)

    for segment in market.get("segments") or []:

        if (
            isinstance(segment, dict)
            and "sourceIds" in segment
        ):
            claims.append(segment)

    return claims


def _source_relevance_by_id(
    results: list,
) -> dict[str, float]:
    """
    Map sourceId to its relevance score.
    """

    sources = compact_sources(
        results,
        limit=MAX_SOURCES_IN_CONTEXT,
    )

    lookup = {}

    for index, source in enumerate(sources):

        if index >= len(results):
            continue

        score = results[index].get(
            "score"
        )

        if isinstance(score, (int, float)):

            lookup[
                source["sourceId"]
            ] = score

    return lookup


def _parse_published_at(
    value,
) -> datetime | None:
    """
    Best-effort ISO-8601 date parser.
    """

    if not isinstance(value, str) or not value:
        return None

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:

        return None

    if parsed.tzinfo is None:

        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def _source_recency(
    results: list,
) -> dict:
    """
    Calculate source recency where published dates exist.
    """

    total = len(results)

    ages_days = []

    for result in results:

        parsed = _parse_published_at(
            result.get("publishedAt")
        )

        if parsed is not None:

            age = (
                datetime.now(timezone.utc)
                - parsed
            ).total_seconds() / 86400

            ages_days.append(age)

    if not ages_days:

        return {
            "sourcesWithKnownDate": 0,
            "totalSources": total,
            "medianAgeDays": None,
        }

    ages_days.sort()

    mid = len(ages_days) // 2

    if len(ages_days) % 2:

        median = ages_days[mid]

    else:

        median = (
            ages_days[mid - 1]
            + ages_days[mid]
        ) / 2

    return {
        "sourcesWithKnownDate": len(
            ages_days
        ),
        "totalSources": total,
        "medianAgeDays": round(
            median,
            1,
        ),
    }


def _confidence_dashboard(
    state: PipelineState,
) -> dict:
    """
    Build confidence dashboard from evidence-backed claims.
    """

    claims = _collect_claims(state)

    total_claims = len(claims)

    cited_ids: set[str] = set()

    claims_with_source = 0
    claims_with_multiple = 0

    for claim in claims:

        source_ids = (
            claim.get("sourceIds")
            or []
        )

        if source_ids:

            claims_with_source += 1
            cited_ids.update(source_ids)

        if len(source_ids) >= 2:

            claims_with_multiple += 1

    def _pct(
        numerator: int,
        denominator: int,
    ) -> int:

        if not denominator:
            return 0

        return round(
            (numerator / denominator)
            * 100
        )

    relevance_by_id = (
        _source_relevance_by_id(
            state.get("results", [])
        )
    )

    cited_scores = [
        relevance_by_id[sid]
        for sid in cited_ids
        if sid in relevance_by_id
    ]

    average_relevance = (
        round(
            sum(cited_scores)
            / len(cited_scores),
            2,
        )
        if cited_scores
        else None
    )

    return {
        "sourceCoverage": {
            "claimsWithSource":
                claims_with_source,
            "totalClaims":
                total_claims,
            "percentage":
                _pct(
                    claims_with_source,
                    total_claims,
                ),
        },

        "averageRelevance":
            average_relevance,

        "crossSourceAgreement": {
            "claimsWithMultipleSources":
                claims_with_multiple,
            "totalClaims":
                total_claims,
            "percentage":
                _pct(
                    claims_with_multiple,
                    total_claims,
                ),
        },

        "directEvidenceRatio": {
            "direct":
                claims_with_source,
            "inferred":
                total_claims
                - claims_with_source,
            "percentage":
                _pct(
                    claims_with_source,
                    total_claims,
                ),
        },

        "sourceRecency":
            _source_recency(
                state.get("results", [])
            ),
    }


def confidence_dashboard_node(
    state: PipelineState,
) -> PipelineState:
    """
    Add claim-level confidence dashboard.
    """

    logger.info(
        "[confidence_dashboard] START"
    )

    if state.get("error"):

        logger.warning(
            "[confidence_dashboard] "
            "Skipped because web search failed"
        )

        return state

    try:

        dashboard = _confidence_dashboard(
            state
        )

    except Exception:

        logger.exception(
            "[confidence_dashboard] FAILED"
        )

        return state

    confidence = {
        **(
            state.get("confidence")
            or {}
        ),
        **dashboard,
    }

    logger.info(
        "[confidence_dashboard] COMPLETE "
        "- source coverage %s%%",
        dashboard[
            "sourceCoverage"
        ]["percentage"],
    )

    return {
        **state,
        "confidence": confidence,
    }


# ============================================================
# NODE TIMER
# ============================================================

def _timed(
    node_name: str,
    fn,
):
    """
    Log wall-clock execution time.
    """

    def wrapper(
        state: PipelineState,
    ) -> PipelineState:

        start = time.time()

        result = fn(state)

        elapsed_ms = round(
            (time.time() - start)
            * 1000
        )

        logger.info(
            "[%s] elapsed_ms=%d",
            node_name,
            elapsed_ms,
        )

        return result

    return wrapper


# ============================================================
# BUILD LANGGRAPH PIPELINE
# ============================================================

def build_pipeline():

    graph = StateGraph(
        PipelineState
    )

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    graph.add_node(
        "web_search",
        _timed(
            "web_search",
            web_search_node,
        ),
    )

    graph.add_node(
        "confidence_indicator",
        _timed(
            "confidence_indicator",
            confidence_node,
        ),
    )

    graph.add_node(
        "market_opportunity",
        _timed(
            "market_opportunity",
            market_opportunity_node,
        ),
    )

    graph.add_node(
        "competitor_discovery",
        _timed(
            "competitor_discovery",
            competitor_discovery_node,
        ),
    )

    graph.add_node(
        "opportunity_score",
        _timed(
            "opportunity_score",
            opportunity_score_node,
        ),
    )

    graph.add_node(
        "white_space",
        _timed(
            "white_space",
            white_space_node,
        ),
    )

    graph.add_node(
        "swot_analysis",
        _timed(
            "swot_analysis",
            swot_node,
        ),
    )

    graph.add_node(
        "mvp_recommendation",
        _timed(
            "mvp_recommendation",
            mvp_node,
        ),
    )

    graph.add_node(
        "gtm_strategy",
        _timed(
            "gtm_strategy",
            gtm_node,
        ),
    )

    graph.add_node(
        "contradiction_detector",
        _timed(
            "contradiction_detector",
            contradiction_detector_node,
        ),
    )

    graph.add_node(
        "confidence_dashboard",
        _timed(
            "confidence_dashboard",
            confidence_dashboard_node,
        ),
    )

    # --------------------------------------------------------
    # PIPELINE FLOW
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "web_search",
    )

    graph.add_edge(
        "web_search",
        "confidence_indicator",
    )

    graph.add_edge(
        "confidence_indicator",
        "market_opportunity",
    )

    graph.add_edge(
        "market_opportunity",
        "competitor_discovery",
    )

    graph.add_edge(
        "competitor_discovery",
        "opportunity_score",
    )

    graph.add_edge(
        "opportunity_score",
        "white_space",
    )

    graph.add_edge(
        "white_space",
        "swot_analysis",
    )

    graph.add_edge(
        "swot_analysis",
        "mvp_recommendation",
    )

    graph.add_edge(
        "mvp_recommendation",
        "gtm_strategy",
    )

    graph.add_edge(
        "gtm_strategy",
        "contradiction_detector",
    )

    graph.add_edge(
        "contradiction_detector",
        "confidence_dashboard",
    )

    graph.add_edge(
        "confidence_dashboard",
        END,
    )

    return graph.compile()


# ============================================================
# FINAL PIPELINE
# ============================================================

pipeline = build_pipeline()