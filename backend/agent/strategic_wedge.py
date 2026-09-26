"""
5-Vector Strategic Wedge Blueprint - Pillar 4 (AFFINITY 5-pillar spec
§4.4, methodology in §2). Attaches whiteSpace.blueprints: for each
top customer segment, an interconnected Friction -> Blindspot -> Tailwind
-> Wedge -> Moat chain plus a numeric conviction % and a key risk.

Deterministic, no LLM call - same "local post-processing over pipeline
artifacts" philosophy white_space.py's own module docstring states: every
vector is read off market_agent.py's segments/trends and
competitor_agent.py's profiled weaknesses, not invented. Runs alongside
analyze_white_space() rather than replacing it - the 3-field opportunity
cards it already produces stay as-is; this is an additional, more
structured view over the same evidence for founders who want the fuller
chain.
"""

_MAX_BLUEPRINTS = 3
_MAX_RISK_LEN = 200


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _dedupe(ids: list[str]) -> list[str]:
    seen, out = set(), []
    for item in ids:
        if isinstance(item, str) and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _source_id_for_url(url: str, results: list) -> str | None:
    for index, result in enumerate(results or [], start=1):
        if isinstance(result, dict) and result.get("url") == url:
            return f"src-{index}"
    return None


def _observed_friction(segment: dict) -> tuple[str, list[str]]:
    pain = _clean(segment.get("painPoints"))
    ids = segment.get("sourceIds") or []
    if pain:
        return pain, ids
    return "The available sources don't clearly describe this segment's pain.", []


def _incumbent_blindspot(competitor: dict | None) -> tuple[str, bool]:
    if competitor is None:
        return "No profiled competitor was available to identify a blindspot from.", False
    weaknesses = [w for w in (competitor.get("weaknesses") or []) if isinstance(w, str) and w.strip()]
    if weaknesses:
        name = competitor.get("name", "the closest competitor")
        return f"{name}: {'; '.join(weaknesses[:2])}", True
    return "Competitor weaknesses were not clear from the available sources.", False


def _structural_tailwind(trends: list) -> tuple[str, list[str]]:
    for trend in trends or []:
        if isinstance(trend, dict):
            text = _clean(trend.get("text"))
            if text:
                return text, trend.get("sourceIds") or []
        elif isinstance(trend, str) and trend.strip():
            return _clean(trend), []
    return "No structural market tailwind was found in the sources.", []


def _asymmetric_wedge(segment: dict) -> tuple[str, bool]:
    motivation = _clean(segment.get("motivations"))
    if motivation:
        return f"Lead with what this segment already wants: {motivation}", True
    return "The sources don't clearly describe what would pull this segment away from incumbents.", False


def _defensibility_moat(competitor_count: int) -> str:
    if competitor_count == 0:
        return "No named competitors were found - the moat is unproven since this could be a real gap or thin search coverage."
    if competitor_count <= 2:
        return f"Only {competitor_count} named competitor(s) were found, leaving room to build lock-in before the space fills in."
    return f"{competitor_count} named competitors were found; the moat depends on switching costs a fast follower can't easily copy."


def _key_risk(blindspot_grounded: bool, wedge_grounded: bool, competitor_count: int) -> str:
    if not blindspot_grounded:
        return "The incumbent blindspot is inferred, not confirmed - a competitor already fixing this would remove the wedge."
    if not wedge_grounded:
        return "This segment's actual pull toward the product is unconfirmed by the sources."
    if competitor_count > 4:
        return "A crowded field means a fast follower could copy the wedge before a moat forms."
    return "Execution speed, not the wedge itself, is the main risk here."


def build_strategic_wedges(
    market_opportunity: dict | None,
    competitors: dict | None,
    results: list | None = None,
) -> dict:
    """Return {"blueprints": [...]} per the spec's whiteSpace.blueprints
    schema (§4.4). Empty list (never a placeholder blueprint) when there
    are no customer segments to build a wedge around.
    """
    market_opportunity = market_opportunity or {}
    competitors = competitors or {}
    results = results or []

    segments = [s for s in (market_opportunity.get("segments") or []) if isinstance(s, dict)]
    trends = market_opportunity.get("trends") or []
    competitor_list = [c for c in (competitors.get("competitors") or []) if isinstance(c, dict)]
    competitor_count = len(competitor_list)
    top_competitor = competitor_list[0] if competitor_list else None

    blueprints = []
    for segment in segments[:_MAX_BLUEPRINTS]:
        name = _clean(segment.get("segment", "this segment"))

        friction, friction_ids = _observed_friction(segment)
        blindspot, blindspot_grounded = _incumbent_blindspot(top_competitor)
        tailwind, tailwind_ids = _structural_tailwind(trends)
        wedge, wedge_grounded = _asymmetric_wedge(segment)
        moat = _defensibility_moat(competitor_count)

        grounded_count = sum(
            [
                bool(friction_ids),
                bool(tailwind_ids),
                blindspot_grounded,
                wedge_grounded,
            ]
        )
        conviction_percent = round(100 * grounded_count / 4)

        source_ids = list(friction_ids) + list(tailwind_ids)
        if top_competitor and top_competitor.get("url"):
            matched = _source_id_for_url(top_competitor["url"], results)
            if matched:
                source_ids.append(matched)

        blueprints.append(
            {
                "opportunityTitle": f"A focused wedge for {name}",
                "segment": name,
                "convictionPercent": conviction_percent,
                "vectors": {
                    "observedFriction": friction,
                    "incumbentBlindspot": blindspot,
                    "structuralTailwind": tailwind,
                    "asymmetricWedge": wedge,
                    "defensibilityMoat": moat,
                },
                "keyRisk": _key_risk(blindspot_grounded, wedge_grounded, competitor_count)[:_MAX_RISK_LEN],
                "supportingSourceIds": _dedupe(source_ids),
            }
        )

    return {"blueprints": blueprints}


__all__ = ["build_strategic_wedges"]
