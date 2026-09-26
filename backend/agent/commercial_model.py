"""
GTM Commercial Architecture - Pillar 5A (AFFINITY 5-pillar spec §4.5A).

Attaches structured unit economics (CAC, ARPU, payback horizon, LTV:CAC)
and a 3-tier pricing table onto gtm.commercialModel. Deterministic, no LLM
call - same reasoning as viability_score.py: these numbers recombine
signals the pipeline already has (the GTM channels' own fitScore,
competitor pricing signals, execution risk from SWOT, and the idea's own
capital-intensity wording), rather than asking a model to invent CAC/ARPU
figures it has no real basis for. The output is an estimate framed as one
(a range, not a false-precision single number), same honesty-first stance
market_agent.py's TAM/SAM/SOM null-when-unsupported rule takes.
"""

import re

_PRICE_TIERS = {
    "low": {"arpu": 19, "tierNames": ("Starter", "Pro", "Scale")},
    "mid": {"arpu": 45, "tierNames": ("Starter", "Pro", "Scale")},
    "high": {"arpu": 99, "tierNames": ("Starter", "Pro", "Scale")},
}

_FIT_MULTIPLIER = {"high": 1.0, "medium": 1.5, "low": 2.2}
_DEFAULT_FIT_MULTIPLIER = 1.8  # no channel data at all - treat acquisition as uncertain, not easy.

# Same capital-intensity wording opportunity_score.py/viability_score.py
# use elsewhere - a capital-heavy delivery model usually means a higher
# price point (enterprise/B2B contracts), a capital-light one usually
# means a lower, self-serve price point.
_CAPITAL_HEAVY_KEYWORDS = (
    "hardware", "device", "sensor", "wearable", "manufactur", "factory", "biotech",
    "drug", "pharma", "clinical", "robot", "vehicle", "drone", "warehouse",
    "logistics", "delivery fleet", "restaurant", "retail store", "satellite",
    "enterprise", "b2b",
)

_CAC_TO_ARPU_MULTIPLE = 3  # a common rule-of-thumb payback target (~3 months of ARPU)
_BASE_LIFETIME_MONTHS = 24  # ceiling on assumed customer lifetime at zero measured execution risk
_MIN_LIFETIME_MONTHS = 6


def _price_tier_source(competitors_data: dict | None) -> str:
    competitors = [c for c in (competitors_data or {}).get("competitors") or [] if isinstance(c, dict)]
    if any(c.get("estimatedPrice") in ("low", "mid", "high") for c in competitors):
        return "competitors"
    return "idea"


def _basis(idea: str, competitors_data: dict | None, channels: list | None, swot_data: dict | None) -> dict:
    """The inputs every number above was derived from, so the UI can show
    founders what drove the estimate (and what to change to move it)
    instead of presenting template figures as if they were measured.
    """
    return {
        "priceTier": _price_tier(idea, competitors_data),
        "priceTierSource": _price_tier_source(competitors_data),
        "channelCount": len([c for c in (channels or []) if isinstance(c, dict)]),
        "executionRiskPercent": int(_execution_risk_percent(swot_data)),
    }


def _price_tier(idea: str, competitors_data: dict | None) -> str:
    """Prefer a real signal from named competitors' own pricing
    (competitor_agent.py's estimatedPrice) over guessing from the idea's
    wording - a competitor whose price is actually known says more about
    what this market will bear than a keyword match on the pitch.
    """
    competitors = [c for c in (competitors_data or {}).get("competitors") or [] if isinstance(c, dict)]
    prices = [c.get("estimatedPrice") for c in competitors if c.get("estimatedPrice") in ("low", "mid", "high")]
    if prices:
        counts = {tier: prices.count(tier) for tier in ("low", "mid", "high")}
        return max(counts, key=counts.get)

    text = (idea or "").lower()
    if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in _CAPITAL_HEAVY_KEYWORDS):
        return "high"
    return "mid"


def _channel_cac_multiplier(channels: list | None) -> float:
    scored = [_FIT_MULTIPLIER[c["fitScore"]] for c in (channels or []) if isinstance(c, dict) and c.get("fitScore") in _FIT_MULTIPLIER]
    if not scored:
        return _DEFAULT_FIT_MULTIPLIER
    return sum(scored) / len(scored)


def _execution_risk_percent(swot_data: dict | None) -> float:
    """0-100, higher = riskier. Local copy of viability_score.py's
    _execution_risk formula (same weight table) - not imported, since that
    module's own worked example above already reuses this exact idea for
    a different metric, and importing it here would tie two independently
    reasoned modules together for one shared formula.
    """
    weight = {"low": 1, "medium": 2, "high": 3, "unknown": 2}
    risks = (swot_data or {}).get("risks") or []
    products = [
        weight.get(r.get("severity"), 2) * weight.get(r.get("likelihood"), 2)
        for r in risks
        if isinstance(r, dict)
    ]
    if not products:
        return 50.0
    return round((sum(products) / len(products)) / 9 * 100)


def _round_to(value: float, nearest: int) -> int:
    return max(nearest, int(round(value / nearest) * nearest))


def _unit_economics(idea: str, competitors_data: dict | None, channels: list | None, swot_data: dict | None) -> dict:
    tier = _price_tier(idea, competitors_data)
    arpu = _PRICE_TIERS[tier]["arpu"]

    multiplier = _channel_cac_multiplier(channels)
    cac_center = arpu * _CAC_TO_ARPU_MULTIPLE * multiplier
    cac_low = _round_to(cac_center * 0.7, 10)
    cac_high = _round_to(cac_center * 1.3, 10)

    payback_center = cac_center / arpu
    payback_low = max(1, round(payback_center * 0.75))
    payback_high = max(payback_low + 1, round(payback_center * 1.25))

    risk_percent = _execution_risk_percent(swot_data)
    lifetime_months = max(_MIN_LIFETIME_MONTHS, round(_BASE_LIFETIME_MONTHS - risk_percent / 100 * (_BASE_LIFETIME_MONTHS - _MIN_LIFETIME_MONTHS)))
    ltv = arpu * lifetime_months
    ltv_to_cac = round(ltv / cac_center, 1) if cac_center else 0.0

    if channels:
        rationale = (
            f"CAC is anchored to a {tier}-tier ARPU of ${arpu}/month, adjusted for the go-to-market "
            "channels' own fit scores - stronger-fit channels imply cheaper acquisition."
        )
    else:
        rationale = (
            f"No go-to-market channels were available yet, so CAC assumes uncertain-cost acquisition "
            f"against a {tier}-tier ARPU of ${arpu}/month."
        )

    return {
        "estimatedCac": f"${cac_low} – ${cac_high}",
        "targetArpu": f"${arpu}/month (${arpu * 12}/year)",
        "paybackHorizonMonths": f"{payback_low} – {payback_high} Months",
        "ltvToCacRatio": f"{ltv_to_cac}x",
        "economicRationale": rationale,
    }


def _pricing_tiers(idea: str, competitors_data: dict | None) -> list[dict]:
    tier = _price_tier(idea, competitors_data)
    arpu = _PRICE_TIERS[tier]["arpu"]
    pro_price = arpu
    scale_price = _round_to(arpu * 3, 10)

    return [
        {
            "tierName": "Starter",
            "price": "$0",
            "billingCycle": "Free Forever",
            "targetSegment": "Solo builders and early adopters",
            "includedFeatures": ["Limited active projects", "Community support"],
        },
        {
            "tierName": "Pro",
            "price": f"${pro_price}",
            "billingCycle": "per month",
            "targetSegment": "Growing teams",
            "includedFeatures": ["Unlimited usage", "Priority support", "Export/reporting"],
        },
        {
            "tierName": "Scale",
            "price": f"${scale_price}",
            "billingCycle": "per month",
            "targetSegment": "Agencies & larger organizations",
            "includedFeatures": ["Team seats", "White-label / API access", "Dedicated support"],
        },
    ]


def build_commercial_model(
    idea: str,
    competitors_data: dict | None = None,
    channels: list | None = None,
    swot_data: dict | None = None,
) -> dict:
    """Return {"unitEconomics": {...}, "pricingTiers": [3 tiers], "basis":
    {...}} per the spec's gtm_strategy.commercialModel schema (§4.5A), plus
    the inputs the estimate was built from.
    """
    return {
        "unitEconomics": _unit_economics(idea, competitors_data, channels, swot_data),
        "pricingTiers": _pricing_tiers(idea, competitors_data),
        "basis": _basis(idea, competitors_data, channels, swot_data),
    }


__all__ = ["build_commercial_model"]
