"""
Founder Action Plan Assembler for Milestone 4 / Track C.

Template-based, no LLM call - assembles a 7/30/90-day plan from the top
SWOT risks, MVP feature priorities, and GTM channels the pipeline already
produced. Same convention as white_space.py/opportunity_score.py/
contradiction_detector.py/experiment_generator.py.

Matches the {"next7Days","next30Days","next90Days"}, each
{"title","items":[{"text": str}]}, contract
frontend/src/components/ExperimentsActionPlan.jsx and its mock fixture
already expect.
"""

_MAX_ITEMS_PER_WINDOW = 3
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
_IMPACT_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _lower_first(text: str) -> str:
    return f"{text[0].lower()}{text[1:]}" if text else text


def _next_7_days(swot: dict | None, mvp: dict | None) -> dict:
    """Cheapest, fastest validation first: the highest-severity risks (or,
    if SWOT produced none, the lowest-effort MVP features) - what a founder
    can actually test within a week.
    """
    risks = sorted(
        [r for r in (swot or {}).get("risks") or [] if isinstance(r, dict) and _clean(r.get("risk"))],
        key=lambda r: _SEVERITY_ORDER.get(r.get("severity"), 3),
    )[:_MAX_ITEMS_PER_WINDOW]

    if risks:
        items = [{"text": f"Validate the risk that {_lower_first(_clean(r['risk']))}."} for r in risks]
    else:
        features = sorted(
            [f for f in (mvp or {}).get("features") or [] if isinstance(f, dict) and _clean(f.get("feature"))],
            key=lambda f: _EFFORT_ORDER.get(f.get("effort"), 3),
        )[:_MAX_ITEMS_PER_WINDOW]
        items = [{"text": f'Run a quick smoke test for "{_clean(f["feature"])}".'} for f in features]

    return {"title": "Test the highest-risk assumptions", "items": items}


def _next_30_days(mvp: dict | None) -> dict:
    """Build the highest-impact, lowest-effort features first - the same
    "smallest useful MVP" philosophy mvp_agent.py's prompt already applies,
    turned into a build sequence.
    """
    features = [f for f in (mvp or {}).get("features") or [] if isinstance(f, dict) and _clean(f.get("feature"))]
    features = sorted(
        features,
        key=lambda f: (_IMPACT_ORDER.get(f.get("impact"), 3), _EFFORT_ORDER.get(f.get("effort"), 3)),
    )[:_MAX_ITEMS_PER_WINDOW]
    items = [{"text": f'Ship "{_clean(f["feature"])}".'} for f in features]
    return {"title": "Build and measure the smallest useful MVP", "items": items}


def _next_90_days(gtm: dict | None) -> dict:
    """Execute the GTM channels gtm_agent.py already recommended, in the
    order it ranked them - no re-ranking here, this just turns the
    existing list into action items.
    """
    channels = [c for c in (gtm or {}).get("channels") or [] if isinstance(c, dict) and _clean(c.get("text"))]
    items = [{"text": f'Run the "{_clean(c["text"])}" channel.'} for c in channels[:_MAX_ITEMS_PER_WINDOW]]
    return {"title": "Execute the strongest evidence-backed GTM channels", "items": items}


def generate_action_plan(gtm: dict | None, mvp: dict | None, swot: dict | None) -> dict:
    """Return a {next7Days, next30Days, next90Days} plan. Each window is
    always a valid {"title", "items"} block even with zero items -
    ExperimentsActionPlan.jsx renders "No action items yet." for an empty
    list rather than hiding the column, so an empty items array is a
    legitimate result, not an error.
    """
    return {
        "next7Days": _next_7_days(swot, mvp),
        "next30Days": _next_30_days(mvp),
        "next90Days": _next_90_days(gtm),
    }
