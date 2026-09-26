"""
Validation Experiment Generator for Milestone 4 / Track C.

Template-based, no LLM call - turns each of the pipeline's top SWOT risks
into a testable hypothesis/method/success-metric triple, grounded in the
lowest-effort MVP feature and the first market segment already produced
upstream. Same convention as white_space.py/opportunity_score.py/
contradiction_detector.py: deterministic post-processing of artifacts the
pipeline already computed, not another Groq call.

Matches the {"hypothesis","method","successMetric","duration","budget",
"relatedRiskIds"} contract frontend/src/components/ExperimentsActionPlan.jsx
and its mock fixture already expect.
"""

_MAX_EXPERIMENTS = 4
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 3}

# effort -> (budget, duration): a low-effort MVP feature is cheap and quick
# to smoke-test; a high-effort one needs a longer, costlier experiment to
# say anything meaningful about it.
_EFFORT_TO_BUDGET_DURATION = {
    "low": ("low", "7 days"),
    "medium": ("medium", "14 days"),
    "high": ("high", "30 days"),
}


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _top_risks(swot: dict | None, limit: int) -> list[dict]:
    risks = [r for r in (swot or {}).get("risks") or [] if isinstance(r, dict) and _clean(r.get("risk"))]
    return sorted(risks, key=lambda r: _SEVERITY_ORDER.get(r.get("severity"), 3))[:limit]


def _top_segment(market_opportunity: dict | None) -> dict | None:
    segments = [s for s in (market_opportunity or {}).get("segments") or [] if isinstance(s, dict)]
    return segments[0] if segments else None


def _cheapest_feature(mvp: dict | None) -> dict | None:
    """The lowest-effort MVP feature is the best fit for an early smoke
    test - cheapest to build a throwaway version of, so it's what this
    generator anchors its experiments to.
    """
    features = [f for f in (mvp or {}).get("features") or [] if isinstance(f, dict) and _clean(f.get("feature"))]
    if not features:
        return None
    return sorted(features, key=lambda f: _EFFORT_ORDER.get(f.get("effort"), 3))[0]


def _hypothesis(risk_text: str, segment: dict | None, feature: dict | None) -> str:
    subject = _clean(segment.get("segment")) if segment else "Target customers"
    if feature:
        return (
            f'{subject} will engage with "{_clean(feature.get("feature"))}" despite the risk that '
            f"{risk_text[0].lower()}{risk_text[1:]}"
        )
    return f"{subject} will respond positively despite the risk that {risk_text[0].lower()}{risk_text[1:]}"


def _method(feature: dict | None, budget: str) -> str:
    if feature:
        return f'Run a {budget}-budget smoke test for "{_clean(feature.get("feature"))}" with a small cohort of target customers.'
    return f"Run a {budget}-budget smoke test (landing page or prototype) with a small cohort of target customers."


def _success_metric(segment: dict | None) -> str:
    subject = _clean(segment.get("segment")) if segment else "qualified visitors"
    return f"At least 10% of {subject} take the target action (sign up, pre-order, or opt in)."


def generate_experiments(
    swot: dict | None, market_opportunity: dict | None, mvp: dict | None
) -> list[dict]:
    """Return up to _MAX_EXPERIMENTS validation experiments, one per
    highest-severity SWOT risk (ties broken by list order), each citing the
    risk it addresses via a synthesized "risk-N" id - risks don't carry a
    stable id of their own upstream, so this assigns one the same way
    frontend/src/mocks/validationMock.js's fixture does (1-indexed, in the
    same severity-sorted order used here).
    """
    risks = _top_risks(swot, _MAX_EXPERIMENTS)
    if not risks:
        return []

    segment = _top_segment(market_opportunity)
    feature = _cheapest_feature(mvp)
    budget, duration = _EFFORT_TO_BUDGET_DURATION.get((feature or {}).get("effort"), ("unknown", "14 days"))

    experiments = []
    for index, risk in enumerate(risks, start=1):
        risk_text = _clean(risk.get("risk"))
        experiments.append(
            {
                "hypothesis": _hypothesis(risk_text, segment, feature),
                "method": _method(feature, budget),
                "successMetric": _success_metric(segment),
                "duration": duration,
                "budget": budget,
                "relatedRiskIds": [f"risk-{index}"],
            }
        )
    return experiments
