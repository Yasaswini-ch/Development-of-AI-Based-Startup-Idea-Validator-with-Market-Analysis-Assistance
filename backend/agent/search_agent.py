import os

from tavily import TavilyClient


class SearchAgentError(Exception):
    """Raised when the Tavily search cannot be completed."""


def _build_query(idea: str, target_customer: str, problem: str) -> str:
    parts = [idea]
    if target_customer:
        parts.append(f"for {target_customer}")
    if problem:
        parts.append(f"solving {problem}")
    parts.append("market size competitors")
    return " ".join(parts)


def _summarize(idea: str, raw_results: list[dict]) -> str:
    if not raw_results:
        return f"No market data found for \"{idea}\"."
    top_titles = ", ".join(r.get("title", "") for r in raw_results[:3] if r.get("title"))
    return f"Found {len(raw_results)} relevant results for \"{idea}\", including: {top_titles}."


def search_market(idea: str, target_customer: str = "", problem: str = "") -> dict:
    """Query Tavily for market/competitor info related to a startup idea.

    Returns: { "summary": str, "results": [{ "title", "snippet", "url" }] }
    Raises: SearchAgentError on missing config or a failed Tavily call.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise SearchAgentError("TAVILY_API_KEY is not configured on the server.")

    query = _build_query(idea, target_customer, problem)

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=5)
    except Exception as exc:  # Tavily SDK raises its own exception types
        raise SearchAgentError(f"Tavily search failed: {exc}") from exc

    raw_results = response.get("results", [])
    results = [
        {
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "url": r.get("url", ""),
        }
        for r in raw_results
    ]

    return {
        "summary": _summarize(idea, raw_results),
        "results": results,
    }
