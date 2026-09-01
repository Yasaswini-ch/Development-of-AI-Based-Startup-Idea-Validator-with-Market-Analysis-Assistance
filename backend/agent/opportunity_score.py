"""
Opportunity Score calculation for Milestone 2.

Computes a simple 0-100 score from:
- Market size signal: 40 points
- Market growth/trend signal: 30 points
- Competitor density: 30 points

This is a heuristic score for comparing startup ideas, not a verified
market valuation.
"""

_MARKET_SIZE_WEIGHT = 40
_GROWTH_WEIGHT = 30
_COMPETITION_WEIGHT = 30


def _market_size_score(market_size: str) -> int:
    """Estimate market-size strength from the grounded market summary."""
    text = (market_size or "").lower()

    strong_signals = (
        "billion",
        "large",
        "global",
        "rapidly growing",
        "high growth",
    )

    medium_signals = (
        "million",
        "growing",
        "regional",
        "expanding",
    )

    if any(signal in text for signal in strong_signals):
        return _MARKET_SIZE_WEIGHT

    if any(signal in text for signal in medium_signals):
        return 25

    if market_size and "not enough" not in text:
        return 15

    return 0


def _growth_score(trends: list) -> int:
    """Score market momentum from the number and quality of trends."""
    if not trends:
        return 0

    positive_signals = (
        "growth",
        "growing",
        "increase",
        "rising",
        "demand",
        "adoption",
        "expanding",
        "surge",
    )

    positive_count = sum(
        1
        for trend in trends
        if any(signal in str(trend).lower() for signal in positive_signals)
    )

    if positive_count >= 3:
        return _GROWTH_WEIGHT

    if positive_count == 2:
        return 22

    if positive_count == 1:
        return 12

    return 6


def _competition_score(competitors: list) -> int:
    """Lower competitor density gives a higher opportunity score."""
    count = len(competitors or [])

    if count == 0:
        return 30
    if count == 1:
        return 24
    if count == 2:
        return 18
    if count == 3:
        return 12

    return 6


def _has_no_grounded_data(market_data: dict, competitor_data: dict) -> bool:
    """True if both upstream agents came back empty - almost certainly a
    failure (rate limit, LLM output rejected), not a genuine "no trends, no
    competitors" market. Without this check, 0 competitors scores as a
    perfect 30/30 ("no competition!"), so a fully-failed analysis would
    otherwise still show a plausible-looking non-zero score - exactly the
    kind of made-up-looking number the rest of this pipeline works hard to
    avoid.
    """
    return (
        not market_data.get("trends")
        and not market_data.get("segments")
        and not competitor_data.get("competitors")
    )


def calculate_opportunity_score(
    market_data: dict | None,
    competitor_data: dict | None,
) -> int:
    """
    Return a composite opportunity score from 0 to 100.

    Weights:
    - Market size: 40
    - Growth/trends: 30
    - Competitor density: 30

    Returns 0 if both upstream agents produced no grounded data at all,
    rather than letting "0 competitors found" masquerade as "no
    competition" when it more likely means the analysis failed.
    """
    market_data = market_data or {}
    competitor_data = competitor_data or {}

    if _has_no_grounded_data(market_data, competitor_data):
        return 0

    market_score = _market_size_score(
        market_data.get("marketSize", "")
    )

    growth_score = _growth_score(
        market_data.get("trends", [])
    )

    competition_score = _competition_score(
        competitor_data.get("competitors", [])
    )

    total = market_score + growth_score + competition_score

    return max(0, min(100, total))
