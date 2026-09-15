"""
Cross-Source Confidence Indicator - Milestone 2.

Uses the relevance scores already produced by retrieval.py.

Output contract:

{
    "marketGrowth": {
        "agree": 3,
        "total": 5
    },
    "competitivePressure": {
        "agree": 2,
        "total": 5
    }
}

This is an evidence-agreement indicator, not a statistical confidence
interval or verified market forecast.
"""

_TREND_SIGNALS = (
    "growth",
    "growing",
    "increase",
    "increasing",
    "rising",
    "rise",
    "demand",
    "adoption",
    "expanding",
    "expansion",
    "surge",
    "rapidly",
)

_COMPETITION_SIGNALS = (
    "competitor",
    "competitors",
    "alternative",
    "alternatives",
    "competing",
    "competition",
    "market leader",
    "market leaders",
    "rival",
    "rivals",
)

_MIN_RELEVANCE = 0.45


def _text_for_result(result: dict) -> str:
    return " ".join(
        [
            str(result.get("title", "")),
            str(result.get("snippet", "")),
        ]
    ).lower()


def _is_relevant(result: dict) -> bool:
    score = result.get("score")

    if not isinstance(score, (int, float)):
        return False

    return score >= _MIN_RELEVANCE


def _contains_signal(result: dict, signals: tuple[str, ...]) -> bool:
    text = _text_for_result(result)
    return any(signal in text for signal in signals)


def calculate_confidence(results: list | None) -> dict:
    """
    Aggregate source-level evidence into the frontend contract.

    Market growth:
      Uses Market size & trends + Industry news sources.

    Competitive pressure:
      Uses Competitors sources.

    A source counts as "agreeing" only when:
      1. its relevance score is above the minimum threshold, and
      2. its text contains a relevant signal.

    The denominator is the number of relevant sources available for
    that topic, so the indicator remains meaningful when only a
    subset of search angles returned useful evidence.
    """

    results = results or []

    market_sources = [
        r
        for r in results
        if r.get("angle") in {
            "Market size & trends",
            "Industry news",
            "Customer demand",
        }
        and _is_relevant(r)
    ]

    competitor_sources = [
        r
        for r in results
        if r.get("angle") == "Competitors"
        and _is_relevant(r)
    ]

    market_agree = sum(
        1
        for r in market_sources
        if _contains_signal(r, _TREND_SIGNALS)
    )

    competition_agree = sum(
        1
        for r in competitor_sources
        if _contains_signal(r, _COMPETITION_SIGNALS)
    )

    return {
        "marketGrowth": {
            "agree": market_agree,
            "total": len(market_sources),
        },
        "competitivePressure": {
            "agree": competition_agree,
            "total": len(competitor_sources),
        },
    }