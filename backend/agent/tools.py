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
import os
import re
import urllib.parse
import urllib.request

from crewai.tools import tool
from ddgs import DDGS
from tavily import TavilyClient

_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "of", "to", "in", "on", "with",
    "is", "are", "market", "size", "growth", "trends", "competitors",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _relevance_score(query: str, title: str, snippet: str) -> float:
    query_words = _keywords(query)
    if not query_words:
        return 0.5
    text_words = _keywords(f"{title} {snippet}")
    overlap = len(query_words & text_words)
    return round(min(1.0, overlap / len(query_words)), 2)


def _from_tavily(query: str, max_results: int) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []

    try:
        response = TavilyClient(api_key=api_key).search(query=query, max_results=max_results)
    except Exception:
        return []

    return [
        {
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "url": r.get("url", ""),
            "score": r.get("score", 0.0),
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
        return []

    return [
        {"title": h.get("title", ""), "snippet": h.get("body", ""), "url": h.get("href", "")}
        for h in hits
        if h.get("href")
    ]


def _from_wikipedia(query: str, max_results: int) -> list[dict]:
    url = f"https://en.wikipedia.org/w/rest.php/v1/search/page?q={urllib.parse.quote(query)}&limit={max_results}"
    try:
        pages = _get_json(url).get("pages", [])
    except Exception:
        return []

    return [
        {
            "title": p.get("title", ""),
            "snippet": (p.get("excerpt") or "").replace('<span class="searchmatch">', "").replace("</span>", ""),
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(p.get('key', ''))}",
        }
        for p in pages
    ]


def _from_hackernews(query: str, max_results: int) -> list[dict]:
    url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&tags=story&hitsPerPage={max_results}"
    try:
        hits = _get_json(url).get("hits", [])
    except Exception:
        return []

    return [
        {
            "title": h.get("title") or h.get("story_title") or "",
            "snippet": h.get("story_text") or f"{h.get('points', 0)} points, {h.get('num_comments', 0)} comments on Hacker News",
            "url": h.get("url") or h.get("story_url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
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

    return [
        {
            "title": r["title"],
            "snippet": r["snippet"],
            "url": r["url"],
            "score": _relevance_score(query, r["title"], r["snippet"]),
        }
        for r in raw
        if r["url"]
    ]


def fetch_results(query: str, max_results: int = 5) -> list[dict]:
    """Tavily first (real relevance score); fall back to the free chain if
    Tavily isn't configured or returns nothing.
    """
    results = _from_tavily(query, max_results)

    if not results:
        results = _free_fallback(query, max_results)

    return [{**r, "query": query} for r in results]


@tool("Web Search")
def web_search(query: str) -> str:
    """Search the web for live market and competitor data related to a startup idea.

    Args:
        query: the search query, e.g. "AI meal planner market size competitors"
    """
    results = fetch_results(query)

    if not results:
        return "No results found."

    lines = [f"- {r['title']}: {r['snippet']} ({r['url']})" for r in results]
    return "\n".join(lines)
