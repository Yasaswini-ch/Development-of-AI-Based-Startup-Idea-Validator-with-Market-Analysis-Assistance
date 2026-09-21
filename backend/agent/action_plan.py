"""
Track C - 7/30/90 Day Action Plan Generator

Generates an execution roadmap based on:
- GTM channels
- MVP priorities/features
- Top risks from SWOT
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _extract_name(value: Any, default: str = "") -> str:
    """Extract a readable name from a string or dictionary."""

    if isinstance(value, str):
        value = value.strip()
        return value if value else default

    if isinstance(value, dict):
        for key in (
            "name",
            "title",
            "channel",
            "feature",
            "risk",
            "description",
        ):
            candidate = value.get(key)

            if isinstance(candidate, str):
                candidate = candidate.strip()

                if candidate:
                    return candidate

    return default


def _extract_items(
    values: list | None,
    defaults: list[str],
) -> list[str]:
    """Convert strings/dictionaries into readable item names."""

    if not values:
        return defaults

    items: list[str] = []

    for value in values:
        name = _extract_name(value)

        if name:
            items.append(name)

    return items if items else defaults


def generate_action_plan(
    gtm: dict | None = None,
    mvp: dict | None = None,
    risks: list | None = None,
) -> dict[str, Any]:
    """
    Generate a practical 7/30/90-day startup action plan.

    Args:
        gtm:
            GTM strategy containing channels.

        mvp:
            MVP recommendation containing features.

        risks:
            Risks identified by SWOT.

    Returns:
        {
            "day7": [...],
            "day30": [...],
            "day90": [...],
            "gtmChannels": [...],
            "mvpPriorities": [...],
            "topRisks": [...]
        }
    """

    gtm = gtm or {}
    mvp = mvp or {}
    risks = risks or []

    # ========================================================
    # GTM CHANNELS
    # ========================================================

    channels = gtm.get("channels") or []

    gtm_channels = _extract_items(
        channels[:5],
        [
            "Direct customer outreach",
            "Content marketing",
            "Community engagement",
            "Pilot partnerships",
        ],
    )

    # ========================================================
    # MVP FEATURES
    # ========================================================

    features = mvp.get("features") or []

    mvp_priorities = _extract_items(
        features[:5],
        [
            "Core MVP workflow",
            "Customer feedback collection",
            "Analytics and recommendations",
        ],
    )

    # ========================================================
    # TOP RISKS
    # ========================================================

    top_risks = _extract_items(
        risks[:5],
        [
            "Customer demand",
            "Product adoption",
            "Competitive differentiation",
        ],
    )

    # ========================================================
    # 7-DAY PLAN
    # ========================================================

    day7 = [
        {
            "task": "Validate the highest-priority customer problem",
            "details": (
                "Conduct customer interviews to understand the frequency, "
                "severity, and current alternatives for the target problem."
            ),
            "priority": "high",
        },
        {
            "task": "Define the minimum viable product scope",
            "details": (
                "Select only the features required to test the core "
                "customer problem."
            ),
            "priority": "high",
        },
        {
            "task": "Prepare initial GTM experiment",
            "details": (
                "Create outreach messaging and test the first acquisition "
                f"channels: {', '.join(gtm_channels[:2])}."
            ),
            "priority": "medium",
        },
        {
            "task": "Define validation metrics",
            "details": (
                "Set measurable targets for customer interviews, MVP usage, "
                "sign-ups, pilot requests, and early engagement."
            ),
            "priority": "medium",
        },
    ]

    # ========================================================
    # 30-DAY PLAN
    # ========================================================

    day30 = [
        {
            "task": "Build and test the MVP",
            "details": (
                "Develop and test the highest-priority product capabilities: "
                f"{', '.join(mvp_priorities[:3])}."
            ),
            "priority": "high",
        },
        {
            "task": "Run customer acquisition experiments",
            "details": (
                "Test the identified GTM channels and compare their ability "
                f"to generate qualified users: {', '.join(gtm_channels)}."
            ),
            "priority": "high",
        },
        {
            "task": "Collect structured customer feedback",
            "details": (
                "Track recurring complaints, feature requests, usability "
                "issues, objections, and reasons for adoption or rejection."
            ),
            "priority": "high",
        },
        {
            "task": "Measure early product validation",
            "details": (
                "Track activation, engagement, retention, conversion, "
                "customer satisfaction, and qualitative feedback."
            ),
            "priority": "medium",
        },
    ]

    # ========================================================
    # 90-DAY PLAN
    # ========================================================

    day90 = [
        {
            "task": "Scale validated acquisition channels",
            "details": (
                "Increase effort on the GTM channels that generate "
                "qualified customers and measurable traction."
            ),
            "priority": "high",
        },
        {
            "task": "Improve the product using customer evidence",
            "details": (
                "Prioritize product improvements based on real user "
                f"feedback around: {', '.join(mvp_priorities)}."
            ),
            "priority": "high",
        },
        {
            "task": "Reduce remaining business risks",
            "details": (
                "Re-test unresolved assumptions and create mitigation "
                f"actions for: {', '.join(top_risks)}."
            ),
            "priority": "high",
        },
        {
            "task": "Define the next growth milestone",
            "details": (
                "Use the first 90 days of customer and product evidence "
                "to define the next product, acquisition, and revenue goals."
            ),
            "priority": "medium",
        },
    ]

    # ========================================================
    # FINAL ACTION PLAN
    # ========================================================

    action_plan = {
        "day7": day7,
        "day30": day30,
        "day90": day90,
        "gtmChannels": gtm_channels,
        "mvpPriorities": mvp_priorities,
        "topRisks": top_risks,
    }

    logger.info(
        "[action_plan] Generated 7/30/90-day action plan"
    )

    return action_plan