from crewai import Agent, Crew, Process, Task

from .llm import get_llm
from .tools import web_search


def build_search_crew(idea: str, target_customer: str, problem: str) -> Crew:
    """One-agent crew for Milestone 1: the Web Search Agent.

    The task's expected_output is deliberately plain prose, not a forced
    structured schema - CrewAI's output_pydantic/function-calling conversion
    proved unreliable with our tested models (Groq would repeatedly fail to
    "call a function" for the conversion step, then silently fall back to
    garbage text). The real, structured search results are fetched directly
    via agent/retrieval.py (which calls agent/tools.py) in graph.py instead,
    so the LLM's only job here is writing a short grounded summary paragraph.

    Future milestones add more agents (Market Opportunity, Competitor Discovery,
    SWOT/Risk, MVP Recommendation, GTM, Report Generation) as additional
    Agent/Task pairs in their own crew-building functions, each wrapped by its own
    LangGraph node in agent/graph.py.
    """
    search_agent = Agent(
        role="Web Search Agent",
        goal="Retrieve live, relevant market and competitor data for a startup idea",
        backstory=(
            "An expert market researcher who grounds every claim in current, "
            "credible sources instead of relying on general knowledge."
        ),
        tools=[web_search],
        llm=get_llm(),
        verbose=False,
    )

    search_task = Task(
        description=(
            f'Search the web for market size, trends, and competitors relevant to '
            f'this startup idea: "{idea}". '
            f"Target customer: {target_customer or 'not specified'}. "
            f"Problem being solved: {problem or 'not specified'}. "
            "Use the Web Search tool at least once to find real, current "
            "sources before answering."
        ),
        expected_output=(
            "A short 2-3 sentence plain-text summary of the market/competitive "
            "landscape based on what the search tool returned. Do not use JSON, "
            "code blocks, or any structured format - just a plain paragraph."
        ),
        agent=search_agent,
    )

    return Crew(
        agents=[search_agent],
        tasks=[search_task],
        process=Process.sequential,
        verbose=False,
    )
