"""
MVP Feature Recommendation Agent for Milestone 3.

Synthesizes prioritized MVP features with effort and impact ratings
derived from white-space gap analysis, market segment needs, and competitor density.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_MVP_FEATURES = 4


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def analyze_mvp_features(
    idea: str,
    target_customer: str,
    problem: str,
    market_opportunity: Optional[Dict[str, Any]] = None,
    white_space: Optional[Dict[str, Any]] = None,
    competitors: Optional[Dict[str, Any]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Derive prioritized MVP feature recommendations with impact and effort ratings."""
    results = results or []
    market_opportunity = market_opportunity or {}
    white_space = white_space or {}
    competitors = competitors or {}

    opportunities = white_space.get("opportunities") or []
    segments = market_opportunity.get("segments") or []
    competitor_list = competitors.get("competitors") or []
    competitor_count = len(competitor_list)

    features = []

    # Feature 1: Core Problem Solution (High Impact, Medium Effort)
    if problem:
        features.append({
            "feature": f"Core Problem Solver: Direct fix for '{problem[:50]}...'",
            "rationale": f"Primary motivation for {target_customer[:40] or 'target users'} to switch from status quo.",
            "impact": "high",
            "effort": "medium",
        })

    # Feature 2: Derived from White-Space Opportunities
    for opp in opportunities[:2]:
        title = _clean(opp.get("title", "Targeted White-Space Feature"))
        why = _clean(opp.get("why", "Addresses identified market gap."))
        features.append({
            "feature": f"Wedge Feature: {title}",
            "rationale": why,
            "impact": "high",
            "effort": "low" if competitor_count <= 1 else "medium",
        })

    # Feature 3: Segment-Specific Onboarding / Workflow Integration
    if segments:
        first_seg = _clean(segments[0].get("segment", "Target Users"))
        features.append({
            "feature": f"Streamlined Onboarding for {first_seg}",
            "rationale": "Reduces friction to initial value realization and boosts day-1 retention.",
            "impact": "medium",
            "effort": "low",
        })

    # Fallback Feature if few were derived
    if len(features) < 2:
        features.append({
            "feature": "Automated Insights & Export Dashboard",
            "rationale": "Enables users to export and share validation results with stakeholders.",
            "impact": "medium",
            "effort": "low",
        })

    return {
        "summary": (
            f"MVP feature set recommended for '{idea[:40]}...'. Designed to maximize market fit "
            f"while minimizing early engineering overhead."
        ),
        "features": features[:_MAX_MVP_FEATURES],
    }
