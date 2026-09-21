"""Non-LLM fallback content for Market Opportunity, SWOT, MVP, and GTM.

Every LLM-backed agent (market/swot/mvp/gtm) can fail for reasons that have
nothing to do with the idea itself: no API key configured yet, every model
in the fallback chain rate limited, or a response that never parses into
valid JSON.

These deterministic fallbacks use only evidence already collected by the
pipeline. They never invent statistics, traction, partnerships, or unsupported
facts.

Every fallback returns:
    "degraded": True

so the frontend can distinguish an automated fallback from a full LLM result.
"""

import re

from .retrieval import _compact_subject


# ============================================================
# Patterns
# ============================================================

_MONEY_PATTERN = re.compile(
    r"\$\s?[\d][\d,]*(?:\.\d+)?\s?"
    r"(?:billion|million|trillion|bn|tn)\b",
    re.IGNORECASE,
)

_GROWTH_PATTERN = re.compile(
    r"\b\d{1,3}(?:\.\d+)?%\s?"
    r"(?:cagr|growth|annually|year[- ]over[- ]year|yoy)\b",
    re.IGNORECASE,
)


# ============================================================
# Common fallback note
# ============================================================

_DEGRADED_NOTE = (
    "Automated evidence-based summary - full AI reasoning is temporarily "
    "unavailable, so this reflects only the signals found directly in the "
    "collected sources, not new analysis."
)


# ============================================================
# Utility helpers
# ============================================================

def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Remove duplicates while preserving original order."""

    seen = set()
    out = []

    for item in items:
        key = item.strip().lower()

        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())

    return out


def _source_id_for_url(
    url: str,
    results: list,
) -> list[str]:
    """
    Match a fallback claim to the sourceId that compact_sources()
    would assign to the corresponding result.

    Source IDs follow the existing src-N convention.
    """

    if not url:
        return []

    for index, result in enumerate(results, start=1):
        if result.get("url") == url:
            return [f"src-{index}"]

    return []


def _claim(
    text: str,
    source_ids: list[str] | None = None,
) -> dict:
    """
    Build a SWOT claim using the same structure as the real
    SWOT agent output.
    """

    return {
        "text": text,
        "sourceIds": source_ids or [],
    }


# ============================================================
# MARKET OPPORTUNITY FALLBACK
# ============================================================

def _market_size_sentence(results: list) -> str:
    """Extract market-size and growth figures from collected sources."""

    market_results = [
        r
        for r in results
        if r.get("angle") == "Market size & trends"
    ]

    text = " ".join(
        f"{r.get('title', '')} {r.get('snippet', '')}"
        for r in market_results
    )

    money_hits = _dedupe_preserve_order(
        _MONEY_PATTERN.findall(text)
    )[:2]

    growth_hits = _dedupe_preserve_order(
        _GROWTH_PATTERN.findall(text)
    )[:2]

    if not money_hits and not growth_hits:
        return (
            f"{_DEGRADED_NOTE} "
            "No clear market-size or growth figures were found "
            "in the available sources."
        )

    parts = []

    if money_hits:
        parts.append(
            "market-size figures mentioned in sources: "
            + ", ".join(money_hits)
        )

    if growth_hits:
        parts.append(
            "growth figures mentioned: "
            + ", ".join(growth_hits)
        )

    return (
        f"{_DEGRADED_NOTE} "
        f"Based on the sources gathered, {'; '.join(parts)}."
    )


def _market_trends(results: list) -> list[dict]:
    """
    Build market trends from collected source titles.

    Each trend follows:

        {
            "text": "...",
            "sourceIds": ["src-1"]
        }
    """

    relevant = [
        r
        for r in results
        if r.get("angle")
        in (
            "Market size & trends",
            "Industry news",
        )
    ]

    seen = set()
    trends = []

    for result in relevant:
        title = (result.get("title") or "").strip()

        key = title.lower()

        if title and key not in seen:
            seen.add(key)

            trends.append(
                {
                    "text": title,
                    "sourceIds": _source_id_for_url(
                        result.get("url", ""),
                        results,
                    ),
                }
            )

    return trends[:4]


def _market_segments(
    target_customer: str,
    problem: str,
    idea: str,
) -> list[dict]:
    """Create a minimal evidence-safe customer segment."""

    target_customer = (target_customer or "").strip()
    problem = (problem or "").strip()

    segment_name = (
        target_customer[:80]
        if target_customer
        else (
            f"Early adopters of "
            f"{_compact_subject(idea, max_words=6)}"
        )
    )

    return [
        {
            "segment": (
                segment_name
                or "General early adopters"
            ),
            "painPoints": (
                problem
                or "Not clear from the sources."
            ),
            "motivations": (
                "Not analyzed - full AI reasoning is temporarily "
                "unavailable, so detailed motivations aren't inferred "
                "for this run."
            ),
            "buyingBehavior": (
                "Not clear from the sources."
            ),
            "sourceIds": [],
        }
    ]


def deterministic_market_opportunity(
    idea: str,
    target_customer: str,
    problem: str,
    results: list,
) -> dict:
    """
    Deterministic fallback for Market Opportunity.
    """

    return {
        "marketSize": _market_size_sentence(results),
        "trends": _market_trends(results),
        "segments": _market_segments(
            target_customer,
            problem,
            idea,
        ),
        "opportunityScore": 0,
        "degraded": True,
    }


# ============================================================
# SWOT FALLBACK
# ============================================================

def deterministic_swot(
    idea: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    white_space: dict | None,
    results: list,
) -> dict:
    """
    Deterministic SWOT fallback.

    Opportunities reuse White-Space output.

    Threats reuse named competitors.

    Source IDs are attached only when a claim can be traced
    back to a specific collected source.
    """

    # --------------------------------------------------------
    # Opportunities
    # --------------------------------------------------------

    ws_opportunities = (
        (white_space or {}).get("opportunities")
        or []
    )

    opportunities = []

    for opp in ws_opportunities[:4]:
        title = (opp.get("title") or "").strip()
        why = (opp.get("why") or "").strip()

        if title:
            opportunities.append(
                _claim(
                    f"{title} - {why}"
                    if why
                    else title
                )
            )

    if not opportunities:
        opportunities = [
            _claim(
                "No specific opportunity gaps were identified "
                "from the available evidence."
            )
        ]

    # --------------------------------------------------------
    # Competitor threats
    # --------------------------------------------------------

    named_competitors = (
        (competitors or {}).get("competitors")
        or []
    )

    if named_competitors:
        threats = [
            _claim(
                (
                    f"Established competitor "
                    f"{c.get('name', 'unnamed')} already offers "
                    f"{c.get('offering') or 'a similar product'}."
                ),
                _source_id_for_url(
                    c.get("url", ""),
                    results,
                ),
            )
            for c in named_competitors[:4]
        ]

    else:
        threats = [
            _claim(
                "No named competitors were identified in the "
                "available sources, so competitive threat level "
                "is unclear."
            )
        ]

    # --------------------------------------------------------
    # Strengths
    # --------------------------------------------------------

    subject = (
        _compact_subject(
            idea,
            max_words=8,
        )
        or "this idea"
    )

    strengths = [
        _claim(
            f"Directly built around a stated, specific problem: "
            f"{subject}."
        )
    ]

    # --------------------------------------------------------
    # Weaknesses
    # --------------------------------------------------------

    weaknesses = [
        _claim(
            "This is an automated fallback summary - deeper, "
            "idea-specific weaknesses require full AI reasoning, "
            "which is temporarily unavailable."
        )
    ]

    # --------------------------------------------------------
    # Risks
    # --------------------------------------------------------

    risks = [
        {
            "risk": (
                "Full AI-driven risk analysis is unavailable "
                "right now; only evidence-derived signals are "
                "shown here."
            ),
            "severity": "unknown",
            "likelihood": "unknown",
            "sourceIds": [],
        }
    ]

    if len(named_competitors) >= 2:
        risks.append(
            {
                "risk": (
                    "Multiple existing competitors were found "
                    "in the available sources, which may raise "
                    "customer acquisition costs."
                ),
                "severity": "medium",
                "likelihood": "medium",
                "sourceIds": [],
            }
        )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "threats": threats,
        "risks": risks,
        "degraded": True,
    }


# ============================================================
# MVP FALLBACK
# ============================================================

def deterministic_mvp(
    idea: str,
    problem: str,
    swot: dict | None,
    market_opportunity: dict | None,
    results: list,
) -> dict:
    """
    Deterministic MVP fallback.

    Uses SWOT opportunities instead of inventing a generic
    feature list.

    Each feature preserves the sourceIds attached to the
    corresponding SWOT opportunity.
    """

    opportunities = (
        (swot or {}).get("opportunities")
        or []
    )

    features = []

    for opp in opportunities[:4]:

        # ----------------------------------------------------
        # Support current dict shape
        # ----------------------------------------------------

        if isinstance(opp, dict):
            opp_text = (
                opp.get("text", "")
                or ""
            )

            opp_source_ids = (
                opp.get("sourceIds", [])
            )

        # ----------------------------------------------------
        # Backward compatibility with old string shape
        # ----------------------------------------------------

        else:
            opp_text = str(opp)
            opp_source_ids = []

        # ----------------------------------------------------
        # Ensure sourceIds is always a list
        # ----------------------------------------------------

        if not isinstance(
            opp_source_ids,
            list,
        ):
            opp_source_ids = []

        # ----------------------------------------------------
        # Create MVP feature
        # ----------------------------------------------------

        features.append(
            {
                "feature": (
                    f"Address: {opp_text[:80]}"
                ),

                "rationale": (
                    "Derived directly from an identified market "
                    "opportunity or evidence gap; AI-prioritized "
                    "rationale is temporarily unavailable."
                ),

                "impact": "unknown",

                "effort": "unknown",

                "sourceIds": opp_source_ids,
            }
        )

    # --------------------------------------------------------
    # No opportunities available
    # --------------------------------------------------------

    if not features:

        subject = (
            _compact_subject(
                idea,
                max_words=8,
            )
            or "the core idea"
        )

        features.append(
            {
                "feature": (
                    f"Core workflow for: {subject}"
                ),

                "rationale": (
                    "A minimal version of the primary workflow "
                    "needed to test the idea's core value "
                    "proposition; specific feature prioritization "
                    "requires full AI reasoning, which is "
                    "temporarily unavailable."
                ),

                "impact": "unknown",

                "effort": "unknown",

                "sourceIds": [],
            }
        )

    return {
        "features": features[:5],
        "degraded": True,
    }


# ============================================================
# GTM FALLBACK
# ============================================================

def deterministic_gtm(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    swot: dict | None,
    results: list,
) -> dict:
    """
    Deterministic GTM fallback.

    Uses simple, testable acquisition tactics and does not
    invent traction, partnerships, revenue, or metrics.

    The results parameter is accepted so the function remains
    compatible with the source-aware GTM agent interface.
    """

    # --------------------------------------------------------
    # Audience
    # --------------------------------------------------------

    audience = (
        (target_customer or "").strip()
        or "early adopters"
    )

    # --------------------------------------------------------
    # Idea subject
    # --------------------------------------------------------

    subject = (
        _compact_subject(
            idea,
            max_words=10,
        )
        or "this idea"
    )

    # --------------------------------------------------------
    # Positioning
    # --------------------------------------------------------

    positioning = (
        f"{subject}, built specifically for {audience}."
    )

    # --------------------------------------------------------
    # Channels
    # --------------------------------------------------------

    channels = [
        (
            f"Direct outreach to {audience} in relevant "
            "online communities and forums"
        ),

        (
            "Content addressing the specific problem "
            "this idea solves"
        ),
    ]

    # --------------------------------------------------------
    # Competitor-based channel
    # --------------------------------------------------------

    named_competitors = (
        (competitors or {}).get("competitors")
        or []
    )

    if named_competitors:

        first_name = (
            named_competitors[0].get(
                "name",
                "existing alternatives",
            )
        )

        channels.append(
            (
                "Comparison content highlighting gaps "
                f"versus {first_name}"
            )
        )

    # --------------------------------------------------------
    # Build final response
    # --------------------------------------------------------

    return {
        "positioning": positioning,

        "positioningSourceIds": [],

        "channels": [
            {
                "text": channel,
                "sourceIds": [],
            }
            for channel in channels[:4]
        ],

        "earlyCustomerApproach": (
            f"Directly recruit and interview a small group "
            f"of {audience} to validate the problem before "
            "investing in wider marketing spend."
        ),

        "earlyCustomerApproachSourceIds": [],

        "degraded": True,
    }