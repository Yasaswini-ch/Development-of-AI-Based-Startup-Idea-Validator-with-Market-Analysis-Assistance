"""Go / no-go verdict - one headline answer at the top of the report.

Every signal needed to answer "should I pursue this?" is already computed
elsewhere in the pipeline (Market Viability Score, Opportunity Score, SWOT
risk severity, the assumption tracker's uncertainty ratings, the
confidence dashboard) - this module only recombines them into a decision,
the reasons behind it, and the single next step. Deterministic, no LLM
call: same reasoning as viability_score.py - no new evidence source, no
new hallucination surface, no extra quota.

Three decisions, deliberately not a pass/fail:
    "pursue"         - strong signals and no unmitigated high-severity risk
    "validate_first" - promising, but something important is still unproven
    "rethink"        - weak market signal or stacked high risks

Returns None when there's no market signal at all (marketOpportunity
failed), rather than issuing a verdict with nothing behind it.
"""

_DECISION_LABELS = {
    "pursue": "Pursue",
    "validate_first": "Validate first",
    "rethink": "Rethink",
}

_HEADLINES = {
    "pursue": "The evidence supports moving ahead with this idea.",
    "validate_first": "Promising, but prove the riskiest assumption before building.",
    "rethink": "The current evidence doesn't support this idea as framed.",
}

# Below this share of claims backed by a cited source, a "pursue" is
# downgraded - a strong score built on thin evidence isn't a green light.
_MIN_CONFIDENCE_FOR_PURSUE = 50

_MAX_REASONS = 4


def _headline_score(market_viability: dict | None, market_opportunity: dict) -> tuple[int | None, str | None]:
    if isinstance(market_viability, dict) and isinstance(market_viability.get("score"), (int, float)):
        return int(market_viability["score"]), "Market viability"
    score = market_opportunity.get("opportunityScore")
    if isinstance(score, (int, float)):
        return int(score), "Opportunity score"
    return None, None


def _high_risks(swot: dict | None) -> list[dict]:
    risks = (swot or {}).get("risks") or []
    return [r for r in risks if isinstance(r, dict) and r.get("severity") == "high"]


def _unproven_assumptions(assumptions: dict | None) -> list[dict]:
    items = (assumptions or {}).get("assumptions") or []
    return [a for a in items if isinstance(a, dict) and a.get("uncertainty") == "high"]


def _confidence_percentage(confidence: dict | None) -> int | None:
    coverage = (confidence or {}).get("sourceCoverage") or {}
    value = coverage.get("percentage")
    if isinstance(value, (int, float)) and coverage.get("totalClaims"):
        return int(value)
    value = (confidence or {}).get("percentage")
    return int(value) if isinstance(value, (int, float)) else None


def build_verdict(
    market_opportunity: dict | None,
    market_viability: dict | None = None,
    swot: dict | None = None,
    assumptions: dict | None = None,
    confidence: dict | None = None,
) -> dict | None:
    if not isinstance(market_opportunity, dict):
        return None

    score, score_name = _headline_score(market_viability, market_opportunity)
    if score is None:
        return None

    high_risks = _high_risks(swot)
    unproven = _unproven_assumptions(assumptions)
    unmitigated = [r for r in high_risks if not (r.get("mitigation") or "").strip()]
    evidence = _confidence_percentage(confidence)

    reasons: list[str] = [f"{score_name} is {score}/100."]

    if score < 40 or len(high_risks) >= 3:
        decision = "rethink"
    elif score >= 65 and not unmitigated and not unproven:
        decision = "pursue"
    else:
        decision = "validate_first"

    if high_risks:
        reasons.append(
            f"{len(high_risks)} high-severity risk{'s' if len(high_risks) != 1 else ''}"
            + (f", {len(unmitigated)} without a mitigation." if unmitigated else ", all with mitigations.")
        )
    if unproven:
        reasons.append(
            f"{len(unproven)} high-uncertainty assumption{'s' if len(unproven) != 1 else ''} still unproven."
        )
    if evidence is not None:
        reasons.append(f"{evidence}% of claims are backed by a cited source.")
        if decision == "pursue" and evidence < _MIN_CONFIDENCE_FOR_PURSUE:
            decision = "validate_first"
            reasons.append("Evidence is too thin to call this a clear go.")
    if market_opportunity.get("degraded"):
        if decision == "pursue":
            decision = "validate_first"
        reasons.append("Market analysis ran in a reduced mode, so treat this verdict as provisional.")

    if unproven:
        next_step = f"Test this first: {unproven[0].get('assumption', '').strip()}"
        how = (unproven[0].get("howToValidate") or "").strip()
        if how:
            next_step = f"{next_step} ({how})"
    elif unmitigated:
        next_step = f"Plan a mitigation for: {unmitigated[0].get('risk', '').strip()}"
    elif decision == "pursue":
        next_step = "Build the smallest MVP from the recommendations below and put it in front of real customers."
    elif decision == "rethink":
        next_step = "Revisit the target customer or problem, then run a new validation."
    else:
        next_step = "Run the top experiment below before committing build time."

    return {
        "decision": decision,
        "label": _DECISION_LABELS[decision],
        "headline": _HEADLINES[decision],
        "score": score,
        "reasons": reasons[:_MAX_REASONS],
        "nextStep": next_step,
    }
