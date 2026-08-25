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
