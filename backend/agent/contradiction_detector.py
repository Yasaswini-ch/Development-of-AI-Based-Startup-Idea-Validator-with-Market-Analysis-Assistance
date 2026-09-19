"""
Contradiction Detector for Milestone 4 / Track B.

Flags apparent tensions across artifacts the pipeline has already computed
(market, SWOT, MVP, GTM) - a local post-processing step, not another LLM
agent, same convention as white_space.py and opportunity_score.py: no extra
Groq call, deterministic, and grounded only in the sourceIds those upstream
agents already attached to their own claims.

This is not proof of an actual contradiction - it's a heuristic surfacing
tensions worth a founder's attention (e.g. "the market is described as
growing, but this segment's buying behavior reads as price-resistant").
Each flag cites the sourceIds of the claims it's built from, so it can be
verified the same way any other claim in this app can.
"""

_MAX_CONTRADICTIONS = 6

_GROWTH_SIGNALS = (
    "growing",
    "growth",
    "expanding",
    "rising",
    "increasing",
    "booming",
    "high growth",
    "rapidly growing",
)

_WEAK_DEMAND_SIGNALS = (
    "not clear from the sources",
    "not clear",
    "not evident",
    "unclear",
    "no clear demand",
    "limited evidence",
    "not tested",
    "unproven",
)

_PREMIUM_SIGNALS = (
    "premium",
    "luxury",
    "high-end",
    "upscale",
    "high-margin",
)

_PRICE_SENSITIVE_SIGNALS = (
    "price-sensitive",
    "price sensitive",
    "budget",
    "affordable",
    "cost-conscious",
    "cost conscious",
    "cheap",
    "low-cost",
    "low cost",
)


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _has_any(text: str, signals: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in signals)


def _claim_text(item) -> str:
    """Trends and similar claims may still be a bare string on stale/
    cached data predating Track A's {"text","sourceIds"} shape (see
    MarketOpportunity.jsx's own typeof guard for the same reason) - handle
    both without crashing.
    """
    if isinstance(item, dict):
        return _clean(item.get("text", ""))
    return _clean(item)


def _claim_source_ids(item) -> list[str]:
    if isinstance(item, dict):
        return item.get("sourceIds") or []
    return []


def _dedupe_source_ids(*id_lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ids in id_lists:
        for source_id in ids:
            if source_id not in seen:
                seen.add(source_id)
                out.append(source_id)
    return out


def _market_growth_vs_weak_demand(market_opportunity: dict | None) -> dict | None:
    """(a) A growing market combined with a segment whose buying behavior
    or motivations read as weak/unproven demand - the market-level story
    and the customer-level evidence are pulling in different directions.
    """
    market_opportunity = market_opportunity or {}
    market_size = _clean(market_opportunity.get("marketSize", ""))
    trends = market_opportunity.get("trends") or []
    trend_texts = [_claim_text(trend) for trend in trends]

    if not _has_any(" ".join([market_size, *trend_texts]), _GROWTH_SIGNALS):
        return None

    for segment in market_opportunity.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        buying_behavior = _clean(segment.get("buyingBehavior", ""))
        motivations = _clean(segment.get("motivations", ""))
        if not (_has_any(buying_behavior, _WEAK_DEMAND_SIGNALS) or _has_any(motivations, _WEAK_DEMAND_SIGNALS)):
            continue

        growth_source_ids = _dedupe_source_ids(*(_claim_source_ids(trend) for trend in trends))
        source_ids = _dedupe_source_ids(growth_source_ids, segment.get("sourceIds") or [])
        segment_name = _clean(segment.get("segment", "")) or "a key customer segment"

        return {
            "type": "marketGrowthVsWeakDemand",
            "summary": (
                f"The market is described as growing, but demand evidence for "
                f'"{segment_name}" reads as weak or unproven - the two claims pull '
                "in different directions."
            ),
            "sourceIds": source_ids,
        }

    return None


def _high_opportunity_vs_high_severity_risks(
    market_opportunity: dict | None, swot: dict | None
) -> dict | None:
    """(b) A high opportunity score alongside several high-severity risks
    from SWOT - the headline number and the risk detail disagree on how
    promising this idea actually is.
    """
    market_opportunity = market_opportunity or {}
    swot = swot or {}
    score = market_opportunity.get("opportunityScore")
    if not isinstance(score, (int, float)) or score < 70:
        return None

    high_severity_risks = [
        risk
        for risk in (swot.get("risks") or [])
        if isinstance(risk, dict) and risk.get("severity") == "high"
    ]
    if len(high_severity_risks) < 2:
        return None

    source_ids = _dedupe_source_ids(*(risk.get("sourceIds") or [] for risk in high_severity_risks))
    risk_summaries = [_clean(risk.get("risk", "")) for risk in high_severity_risks[:3] if risk.get("risk")]

    return {
        "type": "highOpportunityVsHighSeverityRisks",
        "summary": (
            f"Opportunity score is {int(score)}/100, but {len(high_severity_risks)} "
            "risks are rated high severity"
            + (f" ({'; '.join(risk_summaries)})" if risk_summaries else "")
            + " - a strong headline number sitting on top of significant unresolved risk."
        ),
        "sourceIds": source_ids,
    }


def _premium_positioning_vs_price_sensitive_segment(
    gtm: dict | None, market_opportunity: dict | None
) -> dict | None:
    """(c) GTM positioning reads as premium/high-end while a market segment
    reads as price-sensitive - the go-to-market story and the customer
    evidence are targeting different willingness to pay.
    """
    gtm = gtm or {}
    positioning = _clean(gtm.get("positioning", ""))
    if not _has_any(positioning, _PREMIUM_SIGNALS):
        return None

    for segment in (market_opportunity or {}).get("segments") or []:
        if not isinstance(segment, dict):
            continue
        segment_text = " ".join(
            [
                _clean(segment.get("painPoints", "")),
                _clean(segment.get("motivations", "")),
                _clean(segment.get("buyingBehavior", "")),
            ]
        )
        if not _has_any(segment_text, _PRICE_SENSITIVE_SIGNALS):
            continue

        source_ids = _dedupe_source_ids(gtm.get("positioningSourceIds") or [], segment.get("sourceIds") or [])
        segment_name = _clean(segment.get("segment", "")) or "a target segment"

        return {
            "type": "premiumPositioningVsPriceSensitiveSegment",
            "summary": (
                f'GTM positioning reads as premium ("{positioning[:120]}"), but '
                f'"{segment_name}" reads as price-sensitive - worth confirming '
                "willingness to pay before committing to this positioning."
            ),
            "sourceIds": source_ids,
        }

    return None


def _broad_mvp_scope_vs_high_effort_limited_validation(mvp: dict | None) -> dict | None:
    """(d) A broad MVP feature list where most features are both high-effort
    and carry no supporting sourceIds - an ambitious scope resting on thin
    evidence, which is exactly the combination worth trimming first.
    """
    features = (mvp or {}).get("features") or []
    features = [f for f in features if isinstance(f, dict)]
    if len(features) < 4:
        return None

    high_effort = [f for f in features if f.get("effort") == "high"]
    unvalidated = [f for f in features if not (f.get("sourceIds") or [])]
    if len(high_effort) < len(features) / 2 or len(unvalidated) < len(features) / 2:
        return None

    source_ids = _dedupe_source_ids(*(f.get("sourceIds") or [] for f in features))
    feature_names = [_clean(f.get("feature", "")) for f in unvalidated[:3] if f.get("feature")]

    return {
        "type": "broadMvpScopeVsHighEffortLimitedValidation",
        "summary": (
            f"{len(features)} MVP features recommended, and most are both high-effort "
            "and unsupported by any cited source"
            + (f" (e.g. {'; '.join(feature_names)})" if feature_names else "")
            + " - consider narrowing scope to the features with the strongest evidence."
        ),
        "sourceIds": source_ids,
    }


def detect_contradictions(
    market_opportunity: dict | None,
    swot: dict | None,
    mvp: dict | None,
    gtm: dict | None,
) -> list[dict]:
    """Run every contradiction check and return the flags found, capped at
    _MAX_CONTRADICTIONS so a pathological input can't blow up the response.
    Any section that's missing (None, e.g. because that node failed
    upstream) is treated as "nothing to check there" rather than an error -
    each check already tolerates None via its own `or {}`/`or []` defaults.
    """
    checks = (
        _market_growth_vs_weak_demand(market_opportunity),
        _high_opportunity_vs_high_severity_risks(market_opportunity, swot),
        _premium_positioning_vs_price_sensitive_segment(gtm, market_opportunity),
        _broad_mvp_scope_vs_high_effort_limited_validation(mvp),
    )
    return [c for c in checks if c is not None][:_MAX_CONTRADICTIONS]
