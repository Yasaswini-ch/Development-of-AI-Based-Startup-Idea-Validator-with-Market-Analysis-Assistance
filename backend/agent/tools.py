import os

from crewai.tools import tool
from tavily import TavilyClient


def _client() -> TavilyClient:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured on the server.")
    return TavilyClient(api_key=api_key)


def fetch_results(query: str, max_results: int = 5) -> list[dict]:
    """Direct, code-controlled Tavily call - no LLM involved, so results are
    guaranteed to be real data rather than something the model paraphrased or
    invented while trying to format a structured response.
    """
    response = _client().search(query=query, max_results=max_results)
    return [
        {
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "url": r.get("url", ""),
        }
        for r in response.get("results", [])
    ]


@tool("Tavily Web Search")
def tavily_search(query: str) -> str:
    """Search the web for live market and competitor data related to a startup idea.

    Args:
        query: the search query, e.g. "AI meal planner market size competitors"
    """
    results = fetch_results(query)

    if not results:
        return "No results found."

    lines = [f"- {r['title']}: {r['snippet']} ({r['url']})" for r in results]
    return "\n".join(lines)
