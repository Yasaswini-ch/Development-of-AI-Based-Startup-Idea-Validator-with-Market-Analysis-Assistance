from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .crew_agents import build_search_crew


class PipelineState(TypedDict, total=False):
    idea: str
    targetCustomer: str
    problem: str
    summary: str
    results: list
    error: str


def web_search_node(state: PipelineState) -> PipelineState:
    """M1 node: runs the Web Search crew for a summary, and separately
    collects real results across several search angles (not via the LLM) so
    the frontend always shows genuine data instead of something the model
    paraphrased or invented.

    M2+ adds nodes here (market_opportunity_node, competitor_discovery_node, ...) and
    wires them into the graph below, each consuming/producing PipelineState fields per
    docs/architecture.md's agent contracts.
    """
    idea = state["idea"]
    target_customer = state.get("targetCustomer", "")
    problem = state.get("problem", "")

    try:
        results = retrieval.collect(idea, target_customer, problem)
    except Exception as exc:
        return {**state, "error": str(exc)}

    try:
        crew = build_search_crew(idea, target_customer, problem)
        crew_output = crew.kickoff()
        summary = crew_output.raw.strip()
    except Exception:
        # The summary is a nice-to-have on top of the real results above;
        # if the LLM step fails, still return the genuine search results.
        summary = "Here's what we found for your idea based on live web search."

    return {**state, "summary": summary, "results": results}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("web_search", web_search_node)
    graph.add_edge(START, "web_search")
    graph.add_edge("web_search", END)
    return graph.compile()


pipeline = build_pipeline()
