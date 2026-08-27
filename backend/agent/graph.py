from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import retrieval
from .crew_agents import build_search_crew

_REASONING_LEAK_MARKERS = (
    "thought:",
    "action:",
    "final answer",
    "<think",
    "user's prompt",
    "i did it wrong",
    "let me",
    "let's write",
    "double check",
    "i will simply",
    "i need to make sure",
)
_MAX_SUMMARY_LEN = 700


def _strip_reasoning(text: str) -> str:
    """Some reasoning models (e.g. Groq's qwen3.6) emit a <think>...</think>
    block before their real answer. Keep only what comes after the last
    </think> tag, if present.
    """
    marker = "</think>"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    return text.strip()


def _is_clean_summary(text: str) -> bool:
    """Reject anything that still looks like a leaked reasoning trace rather
    than a real answer - a normal 2-3 sentence summary is short and doesn't
    contain ReAct-style scaffolding or meta-commentary about the prompt.
    """
    if not text or len(text) > _MAX_SUMMARY_LEN:
        return False
    lowered = text.lower()
    return not any(marker in lowered for marker in _REASONING_LEAK_MARKERS)


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

    summary = None
    try:
        crew = build_search_crew(idea, target_customer, problem)
        crew_output = crew.kickoff()
        candidate = _strip_reasoning(crew_output.raw)
        if _is_clean_summary(candidate):
            summary = candidate
    except Exception:
        pass

    if summary is None:
        # Either the LLM step failed, or its output still looked like a
        # leaked reasoning trace - fall back to a clean, always-safe summary
        # built from the real results rather than risk showing garbage.
        summary = _fallback_summary(idea, results)

    return {**state, "summary": summary, "results": results}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("web_search", web_search_node)
    graph.add_edge(START, "web_search")
    graph.add_edge("web_search", END)
    return graph.compile()


pipeline = build_pipeline()
