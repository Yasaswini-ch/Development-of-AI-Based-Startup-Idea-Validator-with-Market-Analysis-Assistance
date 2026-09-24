"""
Market Viability Score - Milestone 4 follow-up.

Recombines signals the pipeline already computes elsewhere into one
headline 0-100 score with five sub-metrics, instead of introducing new
LLM-guessed numbers. Every input here is either opportunity_score.py's own
market-size/growth heuristics (already used for the Opportunity Score),
swot_agent.py's risk severity/likelihood ratings, competitor_agent.py's
already-extracted competitor fields, or the confidence dashboard's source
recency stats - no new evidence source, no new hallucination surface.

Deliberately not merged into opportunity_score.py: Opportunity Score
answers "how big is this market," Viability Score answers "how likely is
this specific venture to succeed in it" - overlapping inputs, different
question, so they're kept as two distinct numbers rather than one score
trying to answer both.

Of the five sub-metrics, only marketDemand/executionRisk/growthVelocity
feed the headline `score` - they're directional (higher demand/velocity
and lower risk mean a more viable venture). competitionClarity and timing
are reported alongside them but deliberately excluded from that formula:
they measure how much *is known* about the landscape/moment, not whether
that's good or bad news, so folding a data-quality metric into a
directional viability score would conflate two different questions the
same way merging this file into opportunity_score.py would.
"""

from .opportunity_score import _growth_score, _market_size_score

_DEMAND_WEIGHT = 0.4
_RISK_WEIGHT = 0.3
_VELOCITY_WEIGHT = 0.3

_RISK_LEVEL_WEIGHT = {"low": 1, "medium": 2, "high": 3, "unknown": 2}
_MAX_RISK_PRODUCT = 9  # high (3) severity * high (3) likelihood

# No risk data at all means genuine uncertainty, not "safe" - scored below
# the "unknown"/"unknown" combo (2*2=4/9 ~ 44%) rather than defaulting to 0.
_NO_RISK_DATA_SCORE = 50

# No competitors found is genuinely ambiguous - it could mean a real
# blue-ocean gap or just thin search coverage - so it's scored as
# uncertain-low rather than either extreme, same reasoning as
# _NO_RISK_DATA_SCORE above but lower: unlike a missing risk list (which
# only affects one input), finding zero competitors means the rest of this
# metric (price/breadth clarity) has nothing to measure at all.
_NO_COMPETITOR_DATA_SCORE = 40

# A source dated further back than this contributes ~0 to the recency
# half of the timing score - a year-old signal says little about whether
# *now* is the right time to move.
_MAX_RELEVANT_SOURCE_AGE_DAYS = 365

# No dated sources at all is the same "genuine uncertainty" case as
# _NO_COMPETITOR_DATA_SCORE, just for the timing sub-metric's recency half.
_NO_RECENCY_DATA_SCORE = 40


def _market_demand(market_data: dict) -> int:
    """0-100: market-size and growth-trend strength combined, reusing the
    same heuristics Opportunity Score already scores 0-40/0-30 with here
    just renormalized to a 0-100 scale for this metric.
    """
    market_score = _market_size_score(market_data.get("marketSize", ""))
    growth_score = _growth_score(market_data.get("trends", []))
    return round((market_score + growth_score) / 70 * 100)


def _growth_velocity(market_data: dict) -> int:
    """0-100: growth-trend strength alone, same signal as half of
    _market_demand but surfaced as its own metric since VenturePulse-style
    breakdowns (and founders reading this) expect size and growth reported
    separately, not pre-blended.
    """
    return round(_growth_score(market_data.get("trends", [])) / 30 * 100)


def _execution_risk(swot_data: dict) -> int:
    """0-100: average severity*likelihood across swot_agent.py's risks,
    normalized against the worst possible combination (high*high). Higher
    means riskier - this is the one sub-metric where lower is better, same
    as VenturePulse's "Execution Risk" framing.
    """
    risks = (swot_data or {}).get("risks") or []
    if not risks:
        return _NO_RISK_DATA_SCORE

    products = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        severity = _RISK_LEVEL_WEIGHT.get(risk.get("severity"), _RISK_LEVEL_WEIGHT["unknown"])
        likelihood = _RISK_LEVEL_WEIGHT.get(risk.get("likelihood"), _RISK_LEVEL_WEIGHT["unknown"])
        products.append(severity * likelihood)

    if not products:
        return _NO_RISK_DATA_SCORE

    return round((sum(products) / len(products)) / _MAX_RISK_PRODUCT * 100)


def _competition_clarity(competitors_data: dict) -> int:
    """0-100: how much usable data the pipeline actually has on the
    competitive landscape, not how favorable that landscape is. Each named
    competitor from competitor_agent.py carries an estimatedPrice and
    featureBreadth that are either a real category or "unknown" (NER can
    find a company name in a search snippet without the snippet actually
    saying its price tier or feature scope) - clarity is the fraction of
    named competitors where both fields resolved to real data.
    """
    competitors = (competitors_data or {}).get("competitors") or []
    if not competitors:
        return _NO_COMPETITOR_DATA_SCORE

    resolved = 0
    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        if competitor.get("estimatedPrice") != "unknown" and competitor.get("featureBreadth") != "unknown":
            resolved += 1

    return round(resolved / len(competitors) * 100)


def _timing(market_data: dict, source_recency_data: dict) -> int:
    """0-100: blends growth-trend strength (same signal as half of
    _market_demand - a market that's visibly accelerating is a better
    moment to enter) with how current the evidence behind that trend is
    (the same {"sourcesWithKnownDate", "totalSources", "medianAgeDays"}
    shape the confidence dashboard reports later via
    graph.py's _source_recency - a "growing market" claim resting on
    year-old sources says less about *now* than one backed by recent
    ones). Equally weighted since a strong trend from stale sources and a
    fresh-but-flat trend are both weak timing signals in different ways.

    Takes the recency dict directly (not the full "confidence" state
    field, which is a different, earlier cross-source-agreement
    indicator computed by confidence_node) since viability_score_node
    runs well before the claim-level confidence dashboard does - see
    graph.py.
    """
    growth = _growth_score(market_data.get("trends", [])) / 30 * 100

    median_age_days = (source_recency_data or {}).get("medianAgeDays")
    if median_age_days is None:
        # No dated sources at all - genuine uncertainty, not "stale."
        recency = _NO_RECENCY_DATA_SCORE
    else:
        recency = max(0, 100 - (median_age_days / _MAX_RELEVANT_SOURCE_AGE_DAYS * 100))

    return round((growth + recency) / 2)


def _label(score: int) -> str:
    if score >= 70:
        return "Strong venture potential"
    if score >= 40:
        return "Moderate venture potential"
    return "Early signal"


def calculate_market_viability(
    market_data: dict | None,
    swot_data: dict | None,
    competitors_data: dict | None = None,
    source_recency_data: dict | None = None,
) -> dict:
    """Return {"score", "label", "marketDemand", "executionRisk",
    "growthVelocity", "competitionClarity", "timing"} - all 0-100. Never
    called when marketOpportunity is None (same "don't generate a fake
    score if upstream failed" rule opportunity_score_node already
    follows) - see viability_score_node in graph.py.

    competitors_data/source_recency_data are optional (default None -> the
    same "no data" fallback as an empty dict) so existing callers that
    only care about the original three sub-metrics keep working unchanged;
    the headline `score` itself never depends on them - see this module's
    docstring for why.
    """
    market_data = market_data or {}
    swot_data = swot_data or {}
    competitors_data = competitors_data or {}
    source_recency_data = source_recency_data or {}

    market_demand = _market_demand(market_data)
    growth_velocity = _growth_velocity(market_data)
    execution_risk = _execution_risk(swot_data)
    competition_clarity = _competition_clarity(competitors_data)
    timing = _timing(market_data, source_recency_data)

    score = round(
        _DEMAND_WEIGHT * market_demand
        + _RISK_WEIGHT * (100 - execution_risk)
        + _VELOCITY_WEIGHT * growth_velocity
    )
    score = max(0, min(100, score))

    return {
        "score": score,
        "label": _label(score),
        "marketDemand": market_demand,
        "executionRisk": execution_risk,
        "growthVelocity": growth_velocity,
        "competitionClarity": competition_clarity,
        "timing": timing,
    }
