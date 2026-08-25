import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .crew_agents import build_search_crew
from .schemas import SearchOutput


class PipelineState(TypedDict, total=False):
    idea: str
    targetCustomer: str
    problem: str
    summary: str
    results: list
    error: str


def web_search_node(state: PipelineState) -> PipelineState:
    """M1 node: runs the Web Search crew and folds its structured output into state.

    M2+ adds nodes here (market_opportunity_node, competitor_discovery_node, ...) and
    wires them into the graph below, each consuming/producing PipelineState fields per
    docs/architecture.md's agent contracts.
    """
    try:
        crew = build_search_crew(
            state["idea"], state.get("targetCustomer", ""), state.get("problem", "")
        )
        crew_output = crew.kickoff()
        data = crew_output.pydantic

        if data is None:
            # Some models don't reliably hit CrewAI's structured-output path;
            # fall back to parsing the raw text response as JSON.
            raw = crew_output.raw.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                raw = raw[raw.find("\n") + 1 :] if "\n" in raw else raw
                if raw.lower().startswith("json"):
                    raw = raw[4:]
            data = SearchOutput.model_validate(json.loads(raw))

        return {**state, "summary": data.summary, "results": [r.model_dump() for r in data.results]}
    except Exception as exc:
        return {**state, "error": str(exc)}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("web_search", web_search_node)
    graph.add_edge(START, "web_search")
    graph.add_edge("web_search", END)
    return graph.compile()


pipeline = build_pipeline()
