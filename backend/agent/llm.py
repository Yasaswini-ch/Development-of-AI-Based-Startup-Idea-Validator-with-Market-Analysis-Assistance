import os

DEFAULT_MODEL = "groq/openai/gpt-oss-120b"


def get_llm() -> str:
    """Model string used by every CrewAI agent, via LiteLLM.

    Set LLM_MODEL to override (e.g. "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20241022").
    Groq needs GROQ_API_KEY; OpenAI needs OPENAI_API_KEY; Anthropic needs ANTHROPIC_API_KEY.
    """
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)
