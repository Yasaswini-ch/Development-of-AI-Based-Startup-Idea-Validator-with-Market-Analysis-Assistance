"""
Market Viability Score - Milestone 4 follow-up.

Recombines signals the pipeline already computes elsewhere into one
headline 0-100 score with three sub-metrics, instead of introducing new
LLM-guessed numbers. Every input here is either opportunity_score.py's own
market-size/growth heuristics (already used for the Opportunity Score) or
swot_agent.py's risk severity/likelihood ratings - no new evidence source,
no new hallucination surface.

Deliberately not merged into opportunity_score.py: Opportunity Score
answers "how big is this market," Viability Score answers "how likely is
this specific venture to succeed in it" - overlapping inputs, different
question, so they're kept as two distinct numbers rather than one score
trying to answer both.
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


def _label(score: int) -> str:
    if score >= 70:
        return "Strong venture potential"
    if score >= 40:
        return "Moderate venture potential"
    return "Early signal"


def calculate_market_viability(
    market_data: dict | None,
    swot_data: dict | None,
) -> dict:
    """Return {"score", "label", "marketDemand", "executionRisk",
    "growthVelocity"} - all 0-100. Never called when marketOpportunity is
    None (same "don't generate a fake score if upstream failed" rule
    opportunity_score_node already follows) - see viability_score_node in
    graph.py.
    """
    market_data = market_data or {}
    swot_data = swot_data or {}

    market_demand = _market_demand(market_data)
    growth_velocity = _growth_velocity(market_data)
    execution_risk = _execution_risk(swot_data)

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
    }
