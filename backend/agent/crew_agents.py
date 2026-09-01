from crewai import Agent, Crew, Process, Task

from .llm import get_llm

_MAX_SOURCES_IN_CONTEXT = 10
_MAX_SNIPPET_LEN = 300


def _build_context(results: list) -> str:
    lines = []
    for r in results[:_MAX_SOURCES_IN_CONTEXT]:
        snippet = (r.get("snippet") or "")[:_MAX_SNIPPET_LEN]
        lines.append(f"- {r.get('title', '')}: {snippet}")
    return "\n".join(lines) if lines else "No search results were available."


def build_search_crew(idea: str, target_customer: str, problem: str, results: list) -> Crew:
    """One-agent crew for Milestone 1: the Web Search Agent.

    The agent has no tools - it's given the real, already-fetched search
    results (via agent/retrieval.py) directly as context and only writes a
    short grounded summary on top of them. Earlier this let the LLM call its
    own search tool again, which was a redundant extra API round trip *and*
    an extra multi-turn tool-calling loop that burned through Groq's rate
    limit fast and was the original source of the ReAct-style leaked-
    reasoning bug. Giving it the data directly instead is cheaper, faster,
    and strictly more reliable.

    The task's expected_output is deliberately plain prose, not a forced
    structured schema - CrewAI's output_pydantic/function-calling conversion
    proved unreliable with our tested models (Groq would repeatedly fail to
    "call a function" for the conversion step, then silently fall back to
    garbage text).

    Future milestones add more agents (Market Opportunity, Competitor Discovery,
    SWOT/Risk, MVP Recommendation, GTM, Report Generation) as additional
    Agent/Task pairs in their own crew-building functions, each wrapped by its own
    LangGraph node in agent/graph.py.
    """
    context = _build_context(results)

    search_agent = Agent(
        role="Web Search Agent",
        goal="Summarize live market and competitor data for a startup idea",
        backstory=(
            "An expert market researcher who grounds every claim in current, "
            "credible sources instead of relying on general knowledge."
        ),
        llm=get_llm(),
        verbose=False,
    )

    search_task = Task(
        description=(
            f'Startup idea: "{idea}"\n'
            f"Target customer: {target_customer or 'not specified'}\n"
            f"Problem being solved: {problem or 'not specified'}\n\n"
            "Here are real, current web search results about this idea's market:\n"
            f"{context}\n\n"
            "Summarize the market/competitive landscape based only on the "
            "information above."
        ),
        expected_output=(
            "A short 2-3 sentence plain-text summary. Do not use JSON, code "
            "blocks, or any structured format - just a plain paragraph."
        ),
        agent=search_agent,
    )

    return Crew(
        agents=[search_agent],
        tasks=[search_task],
        process=Process.sequential,
        verbose=False,
    )
