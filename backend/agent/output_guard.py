"""
Shared safeguard against LLM output that leaks internal reasoning instead
of a clean answer - the fix for the exact bug hit in Milestone 1/2 testing
(Groq's qwen3.6 sometimes emits a ReAct-style ramble or a step-by-step
scratchpad instead of a clean response).

market_agent.py and competitor_agent.py use strip_reasoning() before their
own JSON-shape validation (a stronger, more precise check than a text-based
leak detector, since their output must be valid JSON anyway - see those
files). The Web Search Agent's free-text summary used to need its own
text-based leak detector on top of this, but that summary is no longer
LLM-generated at all (see graph.py's _build_summary) - the detector was
removed with it since nothing else needs it.
"""


def strip_reasoning(text: str) -> str:
    """Keep only what comes after the last </think> tag, if present."""
    marker = "</think>"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    return text.strip()
