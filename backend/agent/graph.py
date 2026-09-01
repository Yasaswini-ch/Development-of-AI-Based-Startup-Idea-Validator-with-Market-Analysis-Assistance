from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .crew_agents import build_search_crew
from .market_agent import analyze_market_opportunity
from .output_guard import looks_like_leaked_reasoning, strip_reasoning


def _fallback_summary(idea: str, results: list) -> str:
    if not results:
        return f"No market data found yet for \"{idea}\"."
    angles = sorted({r.get("angle", "") for r in results} - {""})
    coverage = ", ".join(angles) if angles else "the web"
    return (
        f"Found {len(results)} relevant sources for \"{idea}\", covering {coverage}. "
        "See the results below for details."
    )


class PipelineState(TypedDict, total=False):
    idea: str
    targetCustomer: str
    problem: str
    summary: str
    results: list
    marketOpportunity: dict
    error: str


def web_search_node(state: PipelineState) -> PipelineState:
    """M1 node: runs the Web Search crew for a summary, and separately
    collects real results across several search angles (not via the LLM) so
    the frontend always shows genuine data instead of something the model
    paraphrased or invented.
    """
    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")

    try:
        results = retrieval.collect(idea, target_customer, problem)
    except Exception as exc:
        return {**state, "error": str(exc)}

    summary = None
    try:
        crew = build_search_crew(idea, target_customer, problem)
        crew_output = crew.kickoff()
        candidate = strip_reasoning(crew_output.raw)
        if not looks_like_leaked_reasoning(candidate):
            summary = candidate
    except Exception:
        pass

    if summary is None:
        # Either the LLM step failed, or its output still looked like a
        # leaked reasoning trace - fall back to a clean, always-safe summary
        # built from the real results rather than risk showing garbage.
        summary = _fallback_summary(idea, results)

    return {**state, "summary": summary, "results": results}


def market_opportunity_node(state: PipelineState) -> PipelineState:
    """M2 node: Market Opportunity & Customer Segmentation Analysis Agent.

    Consumes the Web Search Agent's results (context passing between agents)
    and asks the LLM to reason about industry size, trends, and target
    segments - grounded in that real data, not invented. Runs after
    web_search in the graph below.
    """
    if state.get("error"):
        return state  # upstream already failed, nothing to add

    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")
    results = state.get("results", [])

    market_opportunity = analyze_market_opportunity(idea, target_customer, problem, results)
    return {**state, "marketOpportunity": market_opportunity}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("web_search", web_search_node)
    graph.add_node("market_opportunity", market_opportunity_node)
    graph.add_edge(START, "web_search")
    graph.add_edge("web_search", "market_opportunity")
    graph.add_edge("market_opportunity", END)
    return graph.compile()


pipeline = build_pipeline()
