"""
Evidence-backed white-space analysis for Milestone 2.

This is deliberately a local post-processing step, not another LLM agent:
the market agent already extracts customer pain points and the competitor
step already identifies named alternatives. White-space analysis combines
those existing signals into founder-readable opportunity gaps without
spending another Groq call.
"""

_MAX_OPPORTUNITIES = 3
_MAX_EVIDENCE_LEN = 180


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _top_source(results: list, preferred_angle: str | None = None) -> dict:
    candidates = results
    if preferred_angle:
        filtered = [r for r in results if r.get("angle") == preferred_angle]
        if filtered:
            candidates = filtered
    if not candidates:
        return {}
    return max(candidates, key=lambda r: r.get("score", 0))


def _source_evidence(source: dict) -> str:
    snippet = _clean(source.get("snippet", ""))
    if not snippet:
        return "Grounded in the retrieved market sources."
    return snippet[:_MAX_EVIDENCE_LEN]


def analyze_white_space(
    market_opportunity: dict | None,
    competitors: dict | None,
    results: list | None = None,
) -> dict:
    """Return opportunity gaps derived from existing pipeline outputs."""
    results = results or []
    market_opportunity = market_opportunity or {}
    competitors = competitors or {}

    segments = market_opportunity.get("segments") or []
    competitor_list = competitors.get("competitors") or []
    competitor_count = len(competitor_list)
    source = _top_source(results, "Customer demand") or _top_source(results)

    opportunities = []
    for segment in segments[:_MAX_OPPORTUNITIES]:
        name = _clean(segment.get("segment", "Underserved customer segment"))
        pain = _clean(segment.get("painPoints", "The sources suggest an unresolved customer pain point."))
        motivation = _clean(segment.get("motivations", "The segment appears motivated to find a better solution."))

        opportunities.append(
            {
                "title": f"Serve {name}",
                "why": pain,
                "fit": motivation,
                "evidence": _source_evidence(source),
            }
        )

    if not opportunities and results:
        opportunities.append(
            {
                "title": "Clarify the highest-intent niche",
                "why": "The search results show market activity, but the available sources did not expose a clear customer segment.",
                "fit": "A focused MVP can validate one narrow user group before expanding.",
                "evidence": _source_evidence(_top_source(results)),
            }
        )

    if competitor_count == 0:
        competition_note = "No named competitors were identified in the available competitor-angle sources."
    elif competitor_count <= 2:
        competition_note = f"Only {competitor_count} named competitor(s) were identified, suggesting room for a focused wedge."
    else:
        competition_note = f"{competitor_count} named competitors were identified, so differentiation should be explicit."

    return {
        "summary": (
            "White-space opportunities are derived from customer pain points, "
            "competitor density, and retrieved source evidence."
        ),
        "competitionNote": competition_note,
        "opportunities": opportunities,
    }
