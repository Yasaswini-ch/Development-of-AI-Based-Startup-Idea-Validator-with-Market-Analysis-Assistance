"""Non-LLM fallback content for Market Opportunity, SWOT, MVP, and GTM.

Every LLM-backed agent (market/swot/mvp/gtm) can fail for reasons that have
nothing to do with the idea itself: no API key configured yet, every model
in the Groq fallback chain rate limited, or a response that never parses
into valid JSON. Before this module, any of those turned into a hard
"This analysis couldn't be completed" - a real answer existed nowhere in
the pipeline, and the founder using the tool got nothing for that section.

These functions are the same honesty-first fallback pattern already used
for Competitor Discovery (real NER, zero LLM cost) and White-Space
(deterministic heuristics) applied to the four agents that previously had
no non-LLM path at all: pull whatever real signal already exists in the
evidence this run collected (search results, White-Space's own triangulated
opportunities, named competitors) and present it plainly, rather than
inventing statistics, segments, or strategy that only a real LLM call could
responsibly produce. Every function here sets `"degraded": True` so the
frontend can show these as a labeled automated summary, never silently
indistinguishable from a full AI-reasoned result.

Called from each agent's public function (see market_agent.py,
swot_agent.py, mvp_agent.py, gtm_agent.py) only after the real LLM call has
already failed or its output didn't parse - never in place of a working
LLM response.
"""

import re

from .retrieval import _compact_subject

_MONEY_PATTERN = re.compile(
    r"\$\s?[\d][\d,]*(?:\.\d+)?\s?(?:billion|million|trillion|bn|tn)\b",
    re.IGNORECASE,
)
_GROWTH_PATTERN = re.compile(
    r"\b\d{1,3}(?:\.\d+)?%\s?(?:cagr|growth|annually|year[- ]over[- ]year|yoy)\b",
    re.IGNORECASE,
)

_DEGRADED_NOTE = (
    "Automated evidence-based summary - full AI reasoning is temporarily "
    "unavailable, so this reflects only the signals found directly in the "
    "collected sources, not new analysis."
)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def _market_size_sentence(results: list) -> str:
    market_results = [r for r in results if r.get("angle") == "Market size & trends"]
    text = " ".join(f"{r.get('title', '')} {r.get('snippet', '')}" for r in market_results)

    money_hits = _dedupe_preserve_order(_MONEY_PATTERN.findall(text))[:2]
    growth_hits = _dedupe_preserve_order(_GROWTH_PATTERN.findall(text))[:2]

    if not money_hits and not growth_hits:
        return (
            f"{_DEGRADED_NOTE} No clear market-size or growth figures were "
            "found in the available sources."
        )

    parts = []
    if money_hits:
        parts.append(f"market-size figures mentioned in sources: {', '.join(money_hits)}")
    if growth_hits:
        parts.append(f"growth figures mentioned: {', '.join(growth_hits)}")
    return f"{_DEGRADED_NOTE} Based on the sources gathered, {'; '.join(parts)}."


def _market_trends(results: list) -> list[dict]:
    """Same {"text", "sourceIds"} claim shape as market_agent.py's real
    LLM output (matching swot_agent.py's established contract) - each trend
    cites the sourceId of the result its title came from, via the same
    src-N numbering compact_sources() would assign (matched by url, see
    _source_id_for_url above), or an empty list if no url match is found.
    """
    relevant = [r for r in results if r.get("angle") in ("Market size & trends", "Industry news")]
    seen = set()
    trends = []
    for r in relevant:
        title = (r.get("title") or "").strip()
        key = title.lower()
        if title and key not in seen:
            seen.add(key)
            trends.append({"text": title, "sourceIds": _source_id_for_url(r.get("url", ""), results)})
    return trends[:4]


def _market_segments(target_customer: str, problem: str, idea: str) -> list[dict]:
    target_customer = (target_customer or "").strip()
    problem = (problem or "").strip()
    segment_name = target_customer[:80] if target_customer else f"Early adopters of {_compact_subject(idea, max_words=6)}"
    return [
        {
            "segment": segment_name or "General early adopters",
            "painPoints": problem or "Not clear from the sources.",
            "motivations": (
                "Not analyzed - full AI reasoning is temporarily unavailable, "
                "so detailed motivations aren't inferred for this run."
            ),
            "buyingBehavior": "Not clear from the sources.",
            "sourceIds": [],
        }
    ]


def deterministic_market_opportunity(idea: str, target_customer: str, problem: str, results: list) -> dict:
    """Same contract as market_agent.analyze_market_opportunity's real
    output (marketSize/trends/segments/opportunityScore), built from
    pattern-matched evidence instead of LLM reasoning. trends and segments
    carry the same {"text"/"segment", ..., "sourceIds"} shape as the real
    LLM path (Milestone 4 / Track A) - see _market_trends/_market_segments.
    """
    return {
        "marketSize": _market_size_sentence(results),
        "trends": _market_trends(results),
        "segments": _market_segments(target_customer, problem, idea),
        "opportunityScore": 0,
        "degraded": True,
    }


def _claim(text: str, source_ids: list[str] | None = None) -> dict:
    """Build one SWOT claim in the {"text", "sourceIds"} shape shared with
    swot_agent.py's real LLM output (docs/unique-features-plan.md §5.1/§3).
    """
    return {"text": text, "sourceIds": source_ids or []}


def _source_id_for_url(url: str, results: list) -> list[str]:
    """Best-effort match: if this fallback-derived claim traces back to one
    of the raw results at a known list position, cite the same "src-N" id
    compact_sources() would assign it (same order, same 1-based index) -
    otherwise an empty list, never a guessed id.
    """
    if not url:
        return []
    for index, result in enumerate(results, start=1):
        if result.get("url") == url:
            return [f"src-{index}"]
    return []


def deterministic_swot(
    idea: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    white_space: dict | None,
    results: list,
) -> dict:
    """Same contract as swot_agent.analyze_swot's real output. Opportunities
    reuse White-Space's own triangulated gaps (already deterministic);
    threats reuse Competitor Discovery's real, NER-identified names - both
    already computed upstream in the mesh, not re-derived here. sourceIds
    are only attached where a claim traces back to a specific result (a
    named competitor's url); everything else gets an empty sourceIds list
    rather than a guessed citation.
    """
    ws_opportunities = (white_space or {}).get("opportunities") or []
    opportunities = []
    for opp in ws_opportunities[:4]:
        title = (opp.get("title") or "").strip()
        why = (opp.get("why") or "").strip()
        if title:
            opportunities.append(_claim(f"{title} - {why}" if why else title))
    if not opportunities:
        opportunities = [_claim("No specific opportunity gaps were identified from the available evidence.")]

    named_competitors = (competitors or {}).get("competitors") or []
    if named_competitors:
        threats = [
            _claim(
                f"Established competitor {c.get('name', 'unnamed')} already offers {c.get('offering') or 'a similar product'}.",
                _source_id_for_url(c.get("url", ""), results),
            )
            for c in named_competitors[:4]
        ]
    else:
        threats = [_claim("No named competitors were identified in the available sources, so competitive threat level is unclear.")]

    subject = _compact_subject(idea, max_words=8) or "this idea"
    strengths = [_claim(f"Directly built around a stated, specific problem: {subject}.")]
    weaknesses = [
        _claim(
            "This is an automated fallback summary - deeper, idea-specific "
            "weaknesses require full AI reasoning, which is temporarily unavailable."
        )
    ]

    risks = [
        {
            "risk": (
                "Full AI-driven risk analysis is unavailable right now; "
                "only evidence-derived signals are shown here."
            ),
            "severity": "unknown",
            "likelihood": "unknown",
            "sourceIds": [],
        }
    ]
    if len(named_competitors) >= 2:
        risks.append(
            {
                "risk": "Multiple existing competitors were found in the available sources, which may raise customer acquisition costs.",
                "severity": "medium",
                "likelihood": "medium",
                "sourceIds": [],
            }
        )

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "threats": threats,
        "risks": risks,
        "degraded": True,
    }


def deterministic_mvp(idea: str, problem: str, swot: dict | None, market_opportunity: dict | None) -> dict:
    """Same contract as mvp_agent.analyze_mvp's real output. Turns SWOT's
    own opportunities (real or deterministic-fallback, either way already
    evidence-grounded) into candidate MVP features instead of inventing a
    generic feature list unrelated to this run's evidence.
    """
    opportunities = (swot or {}).get("opportunities") or []
    features = []
    for opp in opportunities[:4]:
        # swot_agent.py's opportunities are {"text", "sourceIds"} objects
        # (see docs/unique-features-plan.md §5.1), not bare strings - fall
        # back to str() for any older/plain-string shape so this never
        # crashes on a stale cached result.
        opp_text = opp.get("text", "") if isinstance(opp, dict) else str(opp)
        opp_source_ids = opp.get("sourceIds", []) if isinstance(opp, dict) else []
        features.append(
            {
                "feature": f"Address: {opp_text[:80]}",
                "rationale": (
                    "Derived directly from an identified market opportunity or "
                    "evidence gap; AI-prioritized rationale is temporarily unavailable."
                ),
                "impact": "unknown",
                "effort": "unknown",
                "sourceIds": opp_source_ids if isinstance(opp_source_ids, list) else [],
            }
        )

    if not features:
        subject = _compact_subject(idea, max_words=8) or "the core idea"
        features.append(
            {
                "feature": f"Core workflow for: {subject}",
                "rationale": (
                    "A minimal version of the primary workflow needed to test the "
                    "idea's core value proposition; specific feature prioritization "
                    "requires full AI reasoning, which is temporarily unavailable."
                ),
                "impact": "unknown",
                "effort": "unknown",
                "sourceIds": [],
            }
        )

    return {"features": features[:5], "degraded": True}


def deterministic_gtm(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    swot: dict | None,
) -> dict:
    """Same contract as gtm_agent.analyze_gtm's real output. Deliberately
    generic, testable tactics (direct outreach, problem-focused content,
    interviews) rather than any invented traction, partnership, or
    metric - those would violate the same "don't invent traction" rule the
    real LLM prompt is given, and a deterministic fallback has even less
    basis to fabricate them than the LLM does.
    """
    audience = (target_customer or "").strip() or "early adopters"
    subject = _compact_subject(idea, max_words=10) or "this idea"
    positioning = f"{subject}, built specifically for {audience}."

    channels = [
        f"Direct outreach to {audience} in relevant online communities and forums",
        "Content addressing the specific problem this idea solves",
    ]
    named_competitors = (competitors or {}).get("competitors") or []
    if named_competitors:
        first_name = named_competitors[0].get("name", "existing alternatives")
        channels.append(f"Comparison content highlighting gaps versus {first_name}")

    return {
        "positioning": positioning,
        "positioningSourceIds": [],
        "channels": [{"text": channel, "sourceIds": []} for channel in channels[:4]],
        "earlyCustomerApproach": (
            f"Directly recruit and interview a small group of {audience} to "
            "validate the problem before investing in wider marketing spend."
        ),
        "earlyCustomerApproachSourceIds": [],
        "degraded": True,
    }
