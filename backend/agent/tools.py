import os

from crewai.tools import tool
from tavily import TavilyClient


@tool("Tavily Web Search")
def tavily_search(query: str) -> str:
    """Search the web for live market and competitor data related to a startup idea.

    Args:
        query: the search query, e.g. "AI meal planner market size competitors"
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured on the server.")

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=5)
    results = response.get("results", [])

    if not results:
        return "No results found."

    lines = [
        f"- {r.get('title', '')}: {r.get('content', '')} ({r.get('url', '')})"
        for r in results
    ]
    return "\n".join(lines)


def run_web_search(idea: str, target_customer: str, problem: str) -> dict:
    """Direct Tavily call for /validate — returns the {summary, results[]} shape."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY is not configured on the server."}

    if not idea or not idea.strip():
        return {"error": "Idea cannot be empty"}

    query = f"{idea} market size competitors for {target_customer or 'general users'}"

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=5)
    except Exception as e:
        return {"error": f"Tavily search failed: {str(e)}"}

    results = response.get("results", [])
    if not results:
        return {"summary": "No results found.", "results": []}

    formatted = [
        {
            "title": r.get("title", ""),
            "snippet": (r.get("content") or "")[:200],
            "url": r.get("url", "")
        }
        for r in results
    ]
    summary = " ".join(r["snippet"] for r in formatted[:2])

    return {"summary": summary, "results": formatted}
