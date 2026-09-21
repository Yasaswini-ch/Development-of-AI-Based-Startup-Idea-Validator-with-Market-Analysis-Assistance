"""
Track C - Experiment Generator

Generates startup validation experiments using:
- SWOT risks
- Market/customer segments
- MVP features

This module is intentionally deterministic/template-based so it works
without requiring another LLM call.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _extract_name(value: Any, default: str) -> str:
    """Extract a readable name from a string or dictionary."""

    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, dict):
        for key in (
            "name",
            "title",
            "segment",
            "feature",
            "risk",
            "description",
        ):
            candidate = value.get(key)

            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    return default


def generate_experiments(
    risks: list | None = None,
    segments: list | None = None,
    mvp_features: list | None = None,
) -> list[dict[str, Any]]:
    """
    Generate practical startup validation experiments.

    Args:
        risks:
            Risks identified by SWOT.

        segments:
            Customer segments identified by market analysis.

        mvp_features:
            Features identified by MVP analysis.

    Returns:
        A list of structured experiments.
    """

    risks = risks or []
    segments = segments or []
    mvp_features = mvp_features or []

    segment_name = _extract_name(
        segments[0],
        "target customers",
    ) if segments else "target customers"

    feature_name = _extract_name(
        mvp_features[0],
        "the core MVP feature",
    ) if mvp_features else "the core MVP feature"

    risk_name = _extract_name(
        risks[0],
        "the highest-priority business risk",
    ) if risks else "the highest-priority business risk"

    experiments: list[dict[str, Any]] = []

    # ========================================================
    # EXPERIMENT 1
    # ========================================================

    experiments.append(
        {
            "id": "EXP-001",
            "title": "Customer Problem Validation",
            "hypothesis": (
                f"{segment_name} experience the target problem frequently "
                "enough that they actively want a better solution."
            ),
            "method": (
                "Conduct 10-15 structured customer interviews. Ask about "
                "their current workflow, frequency of the problem, existing "
                "solutions, current spending, and willingness to test a new "
                "solution."
            ),
            "successMetric": (
                "At least 60% of interviewed customers confirm that the "
                "problem is frequent or painful, and at least 30% agree to "
                "test an MVP or pilot."
            ),
            "priority": "high",
            "basedOn": {
                "customerSegments": segments[:3],
                "risks": risks[:3],
            },
        }
    )

    # ========================================================
    # EXPERIMENT 2
    # ========================================================

    experiments.append(
        {
            "id": "EXP-002",
            "title": "MVP Feature Validation",
            "hypothesis": (
                f"{feature_name} provides enough value for early users to "
                "adopt the proposed MVP."
            ),
            "method": (
                "Create a lightweight prototype or clickable MVP and run "
                "usability sessions with 5-10 representative users."
            ),
            "successMetric": (
                "At least 70% of test users complete the primary workflow "
                "without major assistance and rate the core experience as "
                "useful."
            ),
            "priority": "high",
            "basedOn": {
                "mvpFeatures": mvp_features[:5],
            },
        }
    )

    # ========================================================
    # EXPERIMENT 3
    # ========================================================

    experiments.append(
        {
            "id": "EXP-003",
            "title": "Demand Validation",
            "hypothesis": (
                "Potential customers will demonstrate measurable interest "
                "when presented with the proposed solution."
            ),
            "method": (
                "Create a simple landing page describing the value "
                "proposition and run targeted outreach or a small campaign "
                "to potential customers."
            ),
            "successMetric": (
                "Generate qualified sign-ups, demo requests, pilot "
                "commitments, or other measurable evidence of demand."
            ),
            "priority": "medium",
            "basedOn": {
                "customerSegments": segments[:3],
                "mvpFeatures": mvp_features[:3],
            },
        }
    )

    # ========================================================
    # EXPERIMENT 4
    # ========================================================

    experiments.append(
        {
            "id": "EXP-004",
            "title": "Highest-Risk Assumption Test",
            "hypothesis": (
                f"The major assumption represented by '{risk_name}' can be "
                "validated or reduced through a focused early experiment."
            ),
            "method": (
                "Design a concierge MVP, manual workflow, prototype, "
                "landing-page test, or customer interview specifically "
                "targeting the highest-risk assumption."
            ),
            "successMetric": (
                "The experiment produces clear evidence supporting or "
                "rejecting the assumption and identifies the next action."
            ),
            "priority": "high",
            "basedOn": {
                "risks": risks[:5],
            },
        }
    )

    logger.info(
        "[experiment_generator] Generated %d experiments",
        len(experiments),
    )

    return experiments