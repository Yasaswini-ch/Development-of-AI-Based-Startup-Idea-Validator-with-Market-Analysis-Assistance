"""Separate per-message LangGraph for the conversational startup advisor."""

import re
from typing import TypedDict

from crewai import Agent, Crew, Process, Task
from langgraph.graph import END, START, StateGraph

from . import retrieval
from .decision_history import summarize_decisions
from .llm import get_llm, kickoff_with_fallback, primary_for, AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER
from .output_guard import strip_reasoning
from .prompts.loader import load_prompt
from .session_store import append_turn, get_session, reserve_chat_request
from .structured_output import compact_json, compact_sources

_SEARCH_TERMS = re.compile(
    r"\b(latest|current|today|recent|news|search|find|look up|new competitor|current price|pricing now)\b",
    re.IGNORECASE,
)
_MAX_REPLY_CHARS = 3000
_MAX_MESSAGE_CHARS = 1200
_MAX_SEARCH_QUERY_CHARS = 300

# Maps a chat question to the report section that already answers it, so the
# frontend can auto-scroll the underlying report into view alongside the
# advisor's reply instead of leaving the answer to stand alone. Ordered most
# specific first (e.g. "how do you compare" before the general "competitor"
# match) since the first matching rule wins. `id` is the DOM id
# ValidationResults.jsx assigns each section; `id: None` means "just switch
# tabs" for sections that aren't pinned to one element (e.g. sources/customers).
_SECTION_RULES: list[tuple[re.Pattern, dict]] = [
    (
        re.compile(r"how (do |does )?(i|we|you) (compare|stack up)|comparison matrix", re.IGNORECASE),
        {"tab": "competitors", "id": "sec-compare", "label": "How you compare"},
    ),
    (
        re.compile(r"\bcompetitor|competition|\brival", re.IGNORECASE),
        {"tab": "competitors", "id": "sec-competitors", "label": "Competitive field"},
    ),
    (
        re.compile(r"\btam\b|total addressable market|market size|market growth|market opportunity", re.IGNORECASE),
        {"tab": "market", "id": "sec-market", "label": "Market signal"},
    ),
    (
        re.compile(r"\bviability\b", re.IGNORECASE),
        {"tab": "market", "id": "sec-dynamics", "label": "Viability breakdown"},
    ),
    (
        re.compile(r"customer segment|\bpersona|target customer|ideal customer|voice of (the )?(market|owner)", re.IGNORECASE),
        {"tab": "customers", "id": None, "label": "Customers"},
    ),
    (
        re.compile(r"white ?space|market gap", re.IGNORECASE),
        {"tab": "gaps", "id": "sec-whitespace", "label": "Whitespace gaps"},
    ),
    (
        re.compile(r"\bswot\b|\bstrength|\bweakness", re.IGNORECASE),
        {"tab": "risks", "id": "sec-swot", "label": "Strengths & exposure"},
    ),
    (
        re.compile(r"bear case|investor objection", re.IGNORECASE),
        {"tab": "risks", "id": "sec-bearcase", "label": "Bear case"},
    ),
    (
        re.compile(r"\bassumption", re.IGNORECASE),
        {"tab": "risks", "id": "sec-assumptions", "label": "Key assumptions"},
    ),
    (
        re.compile(r"\bmvp\b|minimum viable product", re.IGNORECASE),
        {"tab": "build", "id": "sec-mvp", "label": "MVP blueprint"},
    ),
    (
        re.compile(r"\brevenue|pricing model|monetiz", re.IGNORECASE),
        {"tab": "build", "id": "sec-revenue", "label": "Revenue models"},
    ),
    (
        re.compile(r"go.?to.?market|\bgtm\b|launch strategy|how should i launch", re.IGNORECASE),
        {"tab": "build", "id": "sec-gtm", "label": "Go-to-market"},
    ),
    (
        re.compile(r"\btimeline\b|build phase|delivery roadmap", re.IGNORECASE),
        {"tab": "experiments", "id": "sec-timeline", "label": "Build timeline"},
    ),
    (
        re.compile(r"\bexperiment|validation plan|how (do |should )?i (validate|test)", re.IGNORECASE),
        {"tab": "experiments", "id": "sec-experiments", "label": "Validation plan"},
    ),
]


def classify_section(message: str) -> dict | None:
    """Best-effort match from a chat question to the report section it's about.

    Returns None when the question doesn't map to any report section (e.g.
    small talk, or a question the report simply doesn't cover) - the frontend
    then leaves the report view untouched.
    """
    for pattern, section in _SECTION_RULES:
        if pattern.search(message):
            return section
    return None


class ChatRateLimitError(RuntimeError):
    pass


class ChatState(TypedDict, total=False):
    message: str
    context: dict
    history: list
    decisions: list
    needsSearch: bool
    searchQuery: str
    freshResults: list
    reply: str


def interpret_node(state: ChatState) -> ChatState:
    message = state["message"].strip()
    needs_search = bool(_SEARCH_TERMS.search(message))
    context = state.get("context", {})
    idea = context.get("idea", "")
    search_query = f"{idea} {message}".strip()[:_MAX_SEARCH_QUERY_CHARS] if needs_search else ""
    return {**state, "needsSearch": needs_search, "searchQuery": search_query}


def _route_after_interpret(state: ChatState) -> str:
    return "chat_search" if state.get("needsSearch") else "respond"


def chat_search_node(state: ChatState) -> ChatState:
    results = retrieval.collect_scoped(state.get("searchQuery", ""))
    return {**state, "freshResults": results}


def _build_response_crew(message: str, context: str, history: str, decisions: str, fresh: str, model: str) -> Crew:
    advisor = Agent(
        role="Conversational Startup Advisor",
        goal="Answer founder follow-up questions using validated session evidence and clearly label uncertainty.",
        backstory=load_prompt("chat_advisor_system"),
        llm=get_llm(max_tokens=550, model=model),
        max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
        max_iter=AGENT_MAX_ITER,
        verbose=False,
    )
    task = Task(
        description=load_prompt(
            "chat_advisor_task", context=context, history=history, decisions=decisions, fresh=fresh, message=message
        ),
        expected_output=load_prompt("chat_advisor_output"),
        agent=advisor,
    )
    return Crew(agents=[advisor], tasks=[task], process=Process.sequential, verbose=False)


def respond_node(state: ChatState) -> ChatState:
    context = compact_json(state.get("context", {}), max_chars=6500)
    history = compact_json(state.get("history", [])[-6:], max_chars=2500)
    # Recorded pivots/decisions (agent/decision_history.py) give the advisor
    # persistent memory of what changed before the last-6-turns window
    # above, without resending the full transcript to the model.
    decisions = summarize_decisions(state.get("decisions", []))
    fresh = compact_json(compact_sources(state.get("freshResults", []), limit=5), max_chars=2200)
    output = kickoff_with_fallback(
        lambda model: _build_response_crew(state["message"], context, history, decisions, fresh, model),
        primary=primary_for("advisor"),
    )
    reply = strip_reasoning(output.raw).strip()
    if not reply:
        raise ValueError("Advisor returned an empty response.")
    return {**state, "reply": reply[:_MAX_REPLY_CHARS]}


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("interpret", interpret_node)
    graph.add_node("chat_search", chat_search_node)
    graph.add_node("respond", respond_node)
    graph.add_edge(START, "interpret")
    graph.add_conditional_edges(
        "interpret",
        _route_after_interpret,
        {"chat_search": "chat_search", "respond": "respond"},
    )
    graph.add_edge("chat_search", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


chat_turn = build_chat_graph()


def run_chat_turn(session_id: str, message: str) -> str:
    message = message.strip()
    if not message or len(message) > _MAX_MESSAGE_CHARS:
        raise ValueError(f"Message must be between 1 and {_MAX_MESSAGE_CHARS} characters.")

    try:
        reserve_chat_request(session_id)
    except RuntimeError as exc:
        raise ChatRateLimitError(str(exc)) from exc

    session = get_session(session_id)
    state = chat_turn.invoke(
        {
            "message": message,
            "context": session["context"],
            "history": session["history"],
            "decisions": session.get("decisions", []),
        }
    )
    reply = state["reply"]
    append_turn(session_id, message, reply)
    return reply
