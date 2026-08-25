import os

DEFAULT_MODEL = "gemini/gemini-2.0-flash"


def get_llm() -> str:
    """Model string used by every CrewAI agent, via LiteLLM.

    Set LLM_MODEL to override (e.g. "groq/qwen/qwen3.6-27b", "openai/gpt-4o-mini").
    Gemini needs GEMINI_API_KEY; Groq needs GROQ_API_KEY; OpenAI needs OPENAI_API_KEY.
    Switched default from Groq to Gemini for a much higher free-tier rate limit
    (Groq's 8k tokens/min was getting exhausted by a single CrewAI request).
    """
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)
