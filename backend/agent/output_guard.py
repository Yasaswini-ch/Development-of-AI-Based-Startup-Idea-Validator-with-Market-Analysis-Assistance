"""
Shared safeguards against LLM output that leaks internal reasoning instead
of a clean answer. Every agent that asks the LLM for free text or JSON
should run its raw output through these before trusting it - this is the
fix for the exact bug we hit in Milestone 1/2 testing (Groq's qwen3.6
sometimes emits a ReAct-style ramble or a step-by-step scratchpad instead
of a clean response, and keyword-matching alone couldn't keep up with every
new phrasing it invented).

The structural checks below (single line, no markdown scaffolding) turned
out to be far more robust than matching specific phrases - every clean
answer we've seen is one paragraph or one line of JSON with no line breaks
or markdown headers, and every broken one had both.
"""

_REASONING_LEAK_MARKERS = (
    "thought:",
    "action:",
    "final answer",
    "<think",
    "user's prompt",
    "i did it wrong",
    "let me",
    "let's write",
    "let's extract",
    "let's look",
    "let's refine",
    "let's verify",
    "double check",
    "i will simply",
    "i need to make sure",
    "i need to ensure",
    "valid segments",
    "based *only*",
    "output matches",
    "self-cor",
    "ready.",
)


def strip_reasoning(text: str) -> str:
    """Keep only what comes after the last </think> tag, if present."""
    marker = "</think>"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    return text.strip()


def looks_like_leaked_reasoning(text: str, max_len: int = 1100) -> bool:
    """True if this text still looks like a reasoning trace/scratchpad
    rather than a clean answer.

    A real clean answer (whether prose or single-line JSON) never contains
    a line break or markdown bold/heading syntax - those only show up when
    the model is thinking out loud step by step. That structural signal
    catches far more failure modes than any fixed phrase list ever will,
    so it's checked first; the keyword list is a secondary backstop.
    """
    if not text or len(text) > max_len:
        return True
    if "\n" in text or "**" in text:
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in _REASONING_LEAK_MARKERS)
