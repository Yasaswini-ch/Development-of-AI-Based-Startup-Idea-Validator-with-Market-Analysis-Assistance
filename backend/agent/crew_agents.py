from crewai import Agent, Crew, Process, Task

from .schemas import SearchOutput
from .tools import tavily_search


def build_search_crew(idea: str, target_customer: str, problem: str) -> Crew:
    """One-agent crew for Milestone 1: the Web Search Agent.

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
        tools=[tavily_search],
        verbose=False,
    )

    search_task = Task(
        description=(
            f'Search the web for market size, trends, and competitors relevant to '
            f'this startup idea: "{idea}". '
            f"Target customer: {target_customer or 'not specified'}. "
            f"Problem being solved: {problem or 'not specified'}. "
            "Use the Tavily Web Search tool at least once to find real, current "
            "sources before answering."
        ),
        expected_output=(
            "A short 2-3 sentence summary of the market/competitive landscape, plus "
            "a list of the most relevant sources found, each with a title, a "
            "one-line snippet, and the source URL."
        ),
        agent=search_agent,
        output_pydantic=SearchOutput,
    )

    return Crew(
        agents=[search_agent],
        tasks=[search_task],
        process=Process.sequential,
        verbose=False,
    )
