"""
Stage-Gated MVP Delivery Roadmap - Pillar 5B (AFFINITY 5-pillar spec
§4.5B). Attaches mvp_recommendations.deliveryRoadmap: a 3-phase timeline
(Alpha/Beta/GA) with exit-gate milestones and team sizing, built from the
MVP agent's own already-prioritized features rather than a fresh LLM call
- Phase 1 ships the "features" list (the smallest testable slice
mvp_agent.py already picked as P0), Phase 2 folds in niceToHave, and Phase
3 is a fixed "harden and launch" gate every idea needs regardless of its
specific features.
"""

_MIN_WEEKS_PER_PHASE = 3
_WEEKS_PER_FEATURE = {"low": 0.5, "medium": 1.0, "high": 2.0, "unknown": 1.0}

_TEAM_TEMPLATE = [
    {"role": "Full-Stack Engineer", "allocation": "1.0 FTE", "primaryFocus": "Core pipeline & feature implementation"},
    {"role": "Frontend / Product Engineer", "allocation": "1.0 FTE", "primaryFocus": "User-facing flows & UI"},
    {"role": "UI/UX Designer", "allocation": "0.5 FTE", "primaryFocus": "Design system & customer tests"},
]


def _feature_names(items: list | None) -> list[str]:
    return [item["feature"] for item in (items or []) if isinstance(item, dict) and item.get("feature")]


def _phase_weeks(items: list | None, level_key: str = "effort") -> int:
    items = items or []
    if not items:
        return _MIN_WEEKS_PER_PHASE
    total = sum(_WEEKS_PER_FEATURE.get(item.get(level_key, "unknown"), 1.0) for item in items if isinstance(item, dict))
    return max(_MIN_WEEKS_PER_PHASE, round(total))


def build_delivery_roadmap(mvp_data: dict | None) -> dict:
    """Return {"totalTimelineWeeks", "teamComposition", "phases"} per the
    spec's mvp_recommendations.deliveryRoadmap schema. Never called when
    mvp is None (same "don't generate a fake roadmap on failed upstream
    data" rule viability_score_node already follows for marketOpportunity)
    - see mvp_node in graph.py.
    """
    mvp_data = mvp_data or {}
    core_features = [f for f in mvp_data.get("features") or [] if isinstance(f, dict)]
    nice_to_have = [f for f in mvp_data.get("niceToHave") or [] if isinstance(f, dict)]

    phase1_weeks = _phase_weeks(core_features)
    phase2_weeks = _phase_weeks(nice_to_have) if nice_to_have else _MIN_WEEKS_PER_PHASE
    phase3_weeks = _MIN_WEEKS_PER_PHASE

    phases = [
        {
            "phaseName": "Phase 1: Proof of Wedge (Alpha)",
            "durationWeeks": phase1_weeks,
            "coreDeliverables": _feature_names(core_features) or ["Single core workflow validated with real users"],
            "exitGateMilestones": ["10 active users complete the core flow with >60% satisfaction"],
        },
        {
            "phaseName": "Phase 2: Closed Beta Pilot",
            "durationWeeks": phase2_weeks,
            "coreDeliverables": _feature_names(nice_to_have) or ["Expanded feature set based on alpha feedback"],
            "exitGateMilestones": ["3 paying pilot customers or 25 validated idea submissions"],
        },
        {
            "phaseName": "Phase 3: General Availability (GA)",
            "durationWeeks": phase3_weeks,
            "coreDeliverables": ["Self-serve onboarding", "Billing and account management", "Public launch readiness"],
            "exitGateMilestones": ["30-day user retention above 25%"],
        },
    ]

    return {
        "totalTimelineWeeks": sum(p["durationWeeks"] for p in phases),
        "teamComposition": _TEAM_TEMPLATE,
        "phases": phases,
    }


__all__ = ["build_delivery_roadmap"]
