"""
Shared safeguards against LLM output that leaks internal reasoning instead
of a clean answer. Every agent that asks the LLM for free text or JSON
should run its raw output through these before trusting it - this is the
fix for the exact bug we hit in Milestone 1 (Groq's qwen3.6 sometimes
emits a ReAct-style ramble - "Thought:", "Final Answer", stray <think>
tags, meta-commentary about the prompt - instead of a clean response).
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
    "double check",
    "i will simply",
    "i need to make sure",
)


def strip_reasoning(text: str) -> str:
    """Keep only what comes after the last </think> tag, if present."""
    marker = "</think>"
    if marker in text:
        text = text.rsplit(marker, 1)[-1]
    return text.strip()


def looks_like_leaked_reasoning(text: str, max_len: int = 700) -> bool:
    """True if this text still looks like a reasoning trace rather than a
    clean answer - too long, or contains ReAct-style scaffolding/meta talk.
    """
    if not text or len(text) > max_len:
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in _REASONING_LEAK_MARKERS)
