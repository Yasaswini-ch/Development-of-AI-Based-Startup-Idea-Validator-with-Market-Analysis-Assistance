"""
Voice-of-Market excerpts - Pillar 1 (Evidence Grounding & Signal Integrity).

Pulls short verbatim sentences out of the search results' own snippets so
the report can show founders what the market actually says, in its own
words, instead of only hiding those words behind a citation popover.

Deterministic, no LLM call - same reasoning competitor_agent.py uses local
NER instead of a model call: picking the sentence in a snippet that talks
about pain or demand is a keyword problem, and every quote here is copied
from a real source, never paraphrased or generated, so this adds no new
hallucination surface and costs none of the shared Groq quota.

sourceIds use the same canonical "src-N" numbering compact_sources()
assigns by position in the raw `results` list (see structured_output.py),
so a quote's sourceId means the same source everywhere else in the app.
"""

import re
from urllib.parse import urlparse

MAX_QUOTES = 12
_MIN_QUOTE_CHARS = 40
_MAX_QUOTE_CHARS = 220

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")

# Each dimension is checked in this order, so a sentence that both names a
# pain and a growth figure is tagged as friction - the pain is the more
# useful thing to put in front of a founder.
_DIMENSION_KEYWORDS = (
    (
        "Observed Friction",
        (
            "frustrat", "struggl", "pain", "hate", "annoy", "difficult", "hard to",
            "waste", "tedious", "manual", "complain", "churn", "expensive",
            "too slow", "confusing", "broken", "problem", "can't", "cannot",
        ),
    ),
    (
        "Demand Signal",
        (
            "looking for", "wish", "need", "want", "would pay", "willing to pay",
            "demand", "request", "searching for", "alternative to",
        ),
    ),
    (
        "Structural Tailwind",
        (
            "growing", "growth", "cagr", "increas", "rising", "surge", "adoption",
            "billion", "million", "expected to reach", "forecast",
        ),
    ),
)

_NEGATIVE_WORDS = (
    "frustrat", "struggl", "hate", "annoy", "difficult", "waste", "tedious",
    "complain", "churn", "expensive", "too slow", "confusing", "broken",
)
_POSITIVE_WORDS = ("growing", "growth", "increas", "rising", "surge", "love", "popular", "adoption")

# Same shape as _DIMENSION_KEYWORDS but for sentences written from the
# operator's side of the business (running/building/scaling it) instead of
# the customer's side (using/buying it) - lets the report show "here's what
# customers say" next to "here's what people running similar businesses
# say", which are different, equally useful kinds of evidence.
_OWNER_DIMENSION_KEYWORDS = (
    (
        "Operational Friction",
        (
            "hard to hire", "difficult to hire", "difficult to retain", "burn rate",
            "overhead cost", "thin margin", "hard to scale", "staffing is",
            "turnover is high", "managing a team is", "operating cost",
            "cash flow is tight", "hard to keep up with demand",
        ),
    ),
    (
        "Growth & Traction",
        (
            "we scaled", "we grew", "our revenue grew", "we hit $", "our mrr",
            "our arr", "we onboarded", "we expanded", "we doubled", "grew our",
        ),
    ),
    (
        "Strategic Signal",
        (
            "we pivoted", "we raised", "our investors", "we decided to focus",
            "we shifted our strategy", "we bootstrapped", "we launched",
        ),
    ),
)

_OWNER_NEGATIVE_WORDS = (
    "hard to hire", "difficult to hire", "difficult to retain", "burn rate",
    "thin margin", "turnover is high", "cash flow is tight", "hard to scale",
)
_OWNER_POSITIVE_WORDS = ("we scaled", "we grew", "we hit $", "we doubled", "we raised", "we expanded")

# What the quote is actually *about*, orthogonal to which dimension it was
# tagged under - lets the UI cluster "3 quotes about pricing" separately
# from "2 about onboarding" instead of one flat list. Checked in order, so
# the first topic a sentence names wins; anything matching none of these
# falls back to "General".
_THEME_KEYWORDS = (
    ("Pricing & Cost", ("price", "pricing", "expensive", "cost", "afford", "cheap", "subscription", "fee", "pay")),
    ("Integrations & Compatibility", ("integrat", "api", "sync", "compatib", "plugin", "connect")),
    ("Reliability & Support", ("support", "downtime", "bug", "crash", "reliab", "customer service", "outage")),
    ("Onboarding & Usability", ("setup", "onboard", "learning curve", "confusing", "easy to use", "intuitive", "interface", "ui")),
    ("Competition & Alternatives", ("alternative to", "switch from", "compared to", "instead of", "vs ", "versus")),
)


def _theme(sentence: str) -> str:
    lowered = sentence.lower()
    for theme, keywords in _THEME_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return theme
    return "General"


def _source_label(result: dict) -> str:
    """Human-readable attribution: the site's hostname, prefixed with the
    Hacker News / Reddit community name where the host makes that obvious,
    since "who said this" matters more to a founder than a bare URL.
    """
    host = urlparse(str(result.get("url", ""))).hostname or ""
    host = host.removeprefix("www.")
    if "reddit.com" in host:
        return "Reddit thread"
    if "news.ycombinator.com" in host:
        return "Hacker News discussion"
    if host:
        return host
    return str(result.get("title", "")).strip()[:60] or "Web source"


def _tag(sentence: str, keyword_groups=_DIMENSION_KEYWORDS) -> str | None:
    lowered = sentence.lower()
    for dimension, keywords in keyword_groups:
        if any(keyword in lowered for keyword in keywords):
            return dimension
    return None


def _sentiment(sentence: str, dimension: str, friction_dimension: str, negative_words, positive_words) -> str:
    lowered = sentence.lower()
    if dimension == friction_dimension or any(word in lowered for word in negative_words):
        return "negative_towards_incumbent"
    if any(word in lowered for word in positive_words):
        return "positive_market_signal"
    return "neutral"


def _clean(sentence: str) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip().strip("\"'“”")
    # Snippets are often cut mid-sentence by the search provider ("...") -
    # a quote that visibly trails off reads as fabricated, so the trailing
    # ellipsis is dropped rather than shown.
    return sentence.rstrip(".… ").strip()


def _extract_candidates_with(
    results: list, keyword_groups, friction_dimension: str, negative_words, positive_words,
) -> list[dict]:
    candidates = []
    for index, result in enumerate(results or [], start=1):
        if not isinstance(result, dict):
            continue
        snippet = str(result.get("snippet", ""))
        for raw in _SENTENCE_SPLIT.split(snippet):
            sentence = _clean(raw)
            if not (_MIN_QUOTE_CHARS <= len(sentence) <= _MAX_QUOTE_CHARS):
                continue
            dimension = _tag(sentence, keyword_groups)
            if dimension is None:
                continue
            candidates.append(
                {
                    "quote": sentence,
                    "speakerOrSource": _source_label(result),
                    "sourceId": f"src-{index}",
                    "url": str(result.get("url", "")),
                    "sentiment": _sentiment(sentence, dimension, friction_dimension, negative_words, positive_words),
                    "taggedDimension": dimension,
                    "theme": _theme(sentence),
                }
            )
            break  # one quote per source
    return candidates


def _extract_candidates(results: list) -> list[dict]:
    return _extract_candidates_with(results, _DIMENSION_KEYWORDS, "Observed Friction", _NEGATIVE_WORDS, _POSITIVE_WORDS)


def _extract_owner_candidates(results: list) -> list[dict]:
    return _extract_candidates_with(
        results, _OWNER_DIMENSION_KEYWORDS, "Operational Friction", _OWNER_NEGATIVE_WORDS, _OWNER_POSITIVE_WORDS
    )


def _rank_and_cap(candidates: list[dict], keyword_groups, limit: int) -> list[dict]:
    rank = {dimension: position for position, (dimension, _) in enumerate(keyword_groups)}
    candidates.sort(key=lambda quote: rank[quote["taggedDimension"]])
    return candidates[:limit]


def extract_voice_of_market(results: list, limit: int = MAX_QUOTES) -> list[dict]:
    """Return up to `limit` {"quote", "speakerOrSource", "sourceId", "url",
    "sentiment", "taggedDimension", "theme"} excerpts spoken from the
    *customer's* side (using/buying the product), at most one per source so
    a single loud page can't fill the whole section, with friction quotes
    ranked first. Empty list (never a placeholder quote) when no snippet
    contains a usable sentence.
    """
    return _rank_and_cap(_extract_candidates(results), _DIMENSION_KEYWORDS, limit)


def extract_voice_of_owner(results: list, limit: int = MAX_QUOTES) -> list[dict]:
    """Same contract as `extract_voice_of_market`, but for sentences spoken
    from the *operator's* side of a similar business - hiring, margins,
    scaling, funding - so a founder can see what running this kind of
    business is actually like, not only what customers say about using it.
    """
    return _rank_and_cap(_extract_owner_candidates(results), _OWNER_DIMENSION_KEYWORDS, limit)


def _summarize(candidates: list[dict], keyword_groups, results: list) -> dict:
    dimension_counts = {dimension: 0 for dimension, _ in keyword_groups}
    for candidate in candidates:
        dimension_counts[candidate["taggedDimension"]] += 1
    return {
        "dimensionCounts": dimension_counts,
        "sourcesScanned": len([r for r in (results or []) if isinstance(r, dict)]),
        "sourcesWithSignal": len(candidates),
    }


def summarize_voice_of_market(results: list) -> dict:
    """Counts across *every* tagged customer-side sentence found in the
    sources, not just the `MAX_QUOTES` shown as cards - so a founder can see
    "22 friction mentions across 55 sources" even though only a handful of
    quotes fit on screen.

    Returns {"dimensionCounts": {dimension: count}, "sourcesScanned": int,
    "sourcesWithSignal": int}. Every dimension key from _DIMENSION_KEYWORDS
    is always present (zero when unseen) so the frontend never has to
    guess at missing keys.
    """
    return _summarize(_extract_candidates(results), _DIMENSION_KEYWORDS, results)


def summarize_voice_of_owner(results: list) -> dict:
    """Same contract as `summarize_voice_of_market`, counting owner/operator-
    side sentences (see `extract_voice_of_owner`) instead of customer ones.
    """
    return _summarize(_extract_owner_candidates(results), _OWNER_DIMENSION_KEYWORDS, results)


__all__ = [
    "extract_voice_of_market",
    "extract_voice_of_owner",
    "summarize_voice_of_market",
    "summarize_voice_of_owner",
    "MAX_QUOTES",
]
