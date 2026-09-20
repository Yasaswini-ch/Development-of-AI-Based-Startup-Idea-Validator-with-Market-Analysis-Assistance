"""
Web search. Tavily is the primary source - a real, trained relevance score
per result, reliable and fast. DuckDuckGo, Wikipedia, and Hacker News are a
zero-cost fallback chain for when TAVILY_API_KEY isn't set or Tavily itself
fails, so the app still returns something useful rather than erroring out
entirely while waiting on a teammate's key.

The free sources don't provide their own ranking, so results from them get
a computed relevance score instead: word-overlap between the query and each
result's title+snippet, normalized to 0-1.
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from ddgs import DDGS
from tavily import TavilyClient

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "of", "to", "in", "on", "with",
    "is", "are", "market", "size", "growth", "trends", "competitors",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    # Naive stemming (strip a trailing "s") so "cocktails" in a query
    # matches "cocktail" in a title/snippet and vice versa - confirmed
    # live this mismatch alone was dropping genuinely relevant results
    # (a real "Craft Cocktail Subscription Boxes" review) just below the
    # inclusion threshold purely for being singular where the query was
    # plural.
    stemmed = {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words}
    return {w for w in stemmed if w not in _STOPWORDS and len(w) > 2}


def _keyword_weight(word: str) -> float:
    """Longer words carry more of the relevance score than short, generic
    ones - a cheap stand-in for real IDF weighting (no corpus to compute
    real term frequencies from). Every angle query has a fixed generic
    suffix appended (" industry news", " market size growth trends",
    etc. - see retrieval.build_search_angles), so short words like "news"
    or "app" incidentally overlap with almost any unrelated source
    ("BBC News", a random tech article). Confirmed live: a "List of
    serial killers" Wikipedia page scored 0.5 relevance for a todo-app
    query purely from matching "list"/"simple"/"news" - three short,
    generic words, zero real topical overlap. Weighting by length still
    lets a fully generic query fall back to something (weight floors at
    0.3), it just stops a couple of short incidental matches alone from
    producing a misleadingly high score.
    """
    return min(1.0, 0.3 + len(word) / 10)


def _relevance_score(query: str, title: str, snippet: str) -> float:
    query_words = _keywords(query)
    if not query_words:
        return 0.5
    text_words = _keywords(f"{title} {snippet}")
    weights = {w: _keyword_weight(w) for w in query_words}
    matched = query_words & text_words
    overlap_weight = sum(weights[w] for w in matched)
    total_weight = sum(weights.values())
    weighted_ratio = overlap_weight / total_weight
    # A single long/heavy word overlapping (e.g. "subscription") can carry
    # most of `total_weight` alone and cross the inclusion threshold even
    # when the result has nothing to do with the query otherwise - e.g. a
    # "Marvel Legends" Wikipedia page scored 0.38 for a cocktail-business
    # query purely by sharing the word "subscription" (a comics
    # subscription, not a cocktail one). Requiring a real minimum number
    # of distinct matched words (not just a ratio) closes this for BOTH
    # long and short queries - a ratio-only penalty (even dampened with
    # sqrt) was confirmed live to still let a single incidental word pass
    # on a short 2-3 word fallback query, while also needing to be lenient
    # enough not to punish a genuine multi-word partial match on a longer
    # 5-6 word query. A flat "matched >= 2" gate handles both: it doesn't
    # scale with query length, so it's exactly as strict for a short query
    # as a long one.
    if len(query_words) >= 2 and len(matched) < 2:
        return 0.0
    coverage_ratio = len(matched) / len(query_words)
    return round(min(1.0, weighted_ratio * coverage_ratio), 2)


def _from_tavily(query: str, max_results: int) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []

    try:
        response = TavilyClient(api_key=api_key).search(query=query, max_results=max_results)
    except Exception:
        logger.warning("Tavily search failed; using free search providers", exc_info=True)
        return []

    return [
        {
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "url": r.get("url", ""),
            "score": r.get("score", 0.0),
            # Tavily includes this when the source itself exposes a
            # publish date - genuinely absent for a lot of results (a
            # product page, a static company site), so None rather than a
            # guessed date is the honest value here, same as every other
            # provider below.
            "publishedAt": r.get("published_date") or None,
        }
        for r in response.get("results", [])
    ]


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "StartupIdeaValidator/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _from_duckduckgo(query: str, max_results: int) -> list[dict]:
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=max_results))
    except Exception:
        logger.warning("DuckDuckGo search failed for query %r", query, exc_info=True)
        return []

    return [
        # DuckDuckGo's text-search endpoint (unlike its separate news
        # endpoint) doesn't return a publish date for a general web
        # result - explicitly None rather than omitted, so it reads the
        # same as "checked, genuinely unavailable" everywhere else that
        # sets this field.
        {"title": h.get("title", ""), "snippet": h.get("body", ""), "url": h.get("href", ""), "publishedAt": None}
        for h in hits
        if h.get("href")
    ]


# Wikipedia page-title shapes that are structurally never useful for market
# research - index/listicle and disambiguation pages, not articles about a
# real product, company, or market. Confirmed live: "List of serial killers
# by number of victims" surfaced as a "relevant" Competitors-angle result
# for a todo-app query, and a NER pass over disambiguation-page snippets
# tends to pick up the unrelated topics being disambiguated as if they were
# competitors. Filtered by title shape rather than added to a URL denylist
# since the useful "en.wikipedia.org" pages (a real company/product page)
# must stay in the fallback chain.
_WIKIPEDIA_LOW_SIGNAL_TITLE = re.compile(
    r"^list of\b|\(disambiguation\)$|^index of\b|^glossary of\b|^timeline of\b",
    re.IGNORECASE,
)


def _from_wikipedia(query: str, max_results: int) -> list[dict]:
    url = f"https://en.wikipedia.org/w/rest.php/v1/search/page?q={urllib.parse.quote(query)}&limit={max_results}"
    try:
        pages = _get_json(url).get("pages", [])
    except Exception:
        logger.warning("Wikipedia search failed for query %r", query, exc_info=True)
        return []

    return [
        {
            "title": p.get("title", ""),
            "snippet": (p.get("excerpt") or "").replace('<span class="searchmatch">', "").replace("</span>", ""),
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(p.get('key', ''))}",
            # The search endpoint doesn't return a last-modified date (that
            # would need a separate per-page API call) - None, not a guess.
            "publishedAt": None,
        }
        for p in pages
        if not _WIKIPEDIA_LOW_SIGNAL_TITLE.search(p.get("title", ""))
    ]


def _hn_timestamp(hit: dict) -> str | None:
    """Algolia's HN search returns both a "created_at" ISO string and a
    "created_at_i" unix int - prefer the int since it needs no parsing and
    is immune to any format drift; fall back to the ISO string as-is if
    for some reason only that's present. None (not a guess) if neither is.
    """
    created_at_i = hit.get("created_at_i")
    if isinstance(created_at_i, (int, float)):
        return datetime.fromtimestamp(created_at_i, tz=timezone.utc).isoformat()
    return hit.get("created_at") or None


def _from_hackernews(query: str, max_results: int) -> list[dict]:
    url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&tags=story&hitsPerPage={max_results}"
    try:
        hits = _get_json(url).get("hits", [])
    except Exception:
        logger.warning("Hacker News search failed for query %r", query, exc_info=True)
        return []

    return [
        {
            "title": h.get("title") or h.get("story_title") or "",
            "snippet": h.get("story_text") or f"{h.get('points', 0)} points, {h.get('num_comments', 0)} comments on Hacker News",
            "url": h.get("url") or h.get("story_url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            # Algolia's HN API reliably returns this (a real post timestamp,
            # unlike the other free providers) - the one free source that
            # can actually back a recency claim.
            "publishedAt": _hn_timestamp(h),
        }
        for h in hits
        if h.get("title") or h.get("story_title")
    ]


def _free_fallback(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo first, topped up with Wikipedia and Hacker News if thin.
    Only used when Tavily isn't configured or fails.
    """
    raw = _from_duckduckgo(query, max_results)

    if len(raw) < max_results:
        raw += _from_wikipedia(query, max_results - len(raw))

    if len(raw) < max_results:
        raw += _from_hackernews(query, max_results - len(raw))

    scored = [
        {
            "title": r["title"],
            "snippet": r["snippet"],
            "url": r["url"],
            "score": _relevance_score(query, r["title"], r["snippet"]),
            "publishedAt": r.get("publishedAt"),
        }
        for r in raw
        if r["url"]
    ]
    return [result for result in scored if result["score"] >= 0.3]


def fetch_results(query: str, max_results: int = 5) -> list[dict]:
    """Tavily first (real relevance score); fall back to the free chain if
    Tavily isn't configured or returns nothing.
    """
    results = _from_tavily(query, max_results)

    if not results:
        results = _free_fallback(query, max_results)

    return [{**r, "query": query} for r in results]
