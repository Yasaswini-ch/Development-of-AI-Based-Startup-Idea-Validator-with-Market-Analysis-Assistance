"""Advisor Decision History (Milestone 4 Track G.1, unique-features-plan.md
§5.6) - a lightweight pass over the chat transcript that records pivots and
decisions as they happen, so the advisor can carry persistent memory of what
changed from the original idea without resending the full transcript every
turn. chat_graph.py's respond_node already caps raw history to the last 6
turns for the LLM prompt - this is what covers everything before that
window, without paying for another LLM call just to summarize it.

Deterministic keyword/pattern matching, no LLM call - same tradeoff as
confidence.py/contradiction_detector.py/opportunity_score.py: a founder's
own phrasing when they change direction ("let's pivot to...", "what if we
target...", "instead of X, focus on Y") is regular enough that pattern
matching catches the common cases without needing a second model call per
chat turn.
"""

import re

_MAX_DECISION_CHARS = 200
_MAX_STORED_DECISIONS = 20

# Deliberately permissive over strict: a false positive costs one extra
# harmless line in the decision log; a false negative silently loses a real
# pivot the advisor should have remembered.
_PIVOT_PATTERNS = re.compile(
    r"\b("
    r"pivot(?:ing|ed)?\s+(?:to|toward|into)|"
    r"let'?s\s+(?:focus on|go with|target|try|build|switch to)|"
    r"instead of|"
    r"what if we|"
    r"switch(?:ing|ed)?\s+to|"
    r"(?:decided|deciding)\s+to|"
    r"exploring\s+(?:an?|the)\s+\w+\s+(?:pivot|option|angle|direction)|"
    r"rather than|"
    r"shift(?:ing|ed)?\s+(?:our\s+)?focus|"
    r"going with|"
    r"chang(?:e|ing|ed)\s+(?:our\s+)?(?:direction|approach|mind|strategy)"
    r")\b",
    re.IGNORECASE,
)


def extract_decision(message: str) -> str | None:
    """Returns a trimmed decision string if `message` reads as a pivot or
    decision, else None."""
    message = message.strip()
    if not message or not _PIVOT_PATTERNS.search(message):
        return None
    return message[:_MAX_DECISION_CHARS]


def append_decision(decisions: list[dict], message: str, timestamp: float) -> list[dict]:
    """Returns a new decisions list with `message` appended if it reads as a
    pivot, else the original list unchanged (never mutated in place, same
    convention session_store.py's own history list follows)."""
    text = extract_decision(message)
    if text is None:
        return decisions
    updated = decisions + [{"text": text, "at": timestamp}]
    return updated[-_MAX_STORED_DECISIONS:]


def summarize_decisions(decisions: list[dict]) -> str:
    """Compact, prompt-ready summary of recorded decisions, oldest first -
    threaded into the advisor prompt instead of the full transcript."""
    if not decisions:
        return "None recorded yet."
    return "\n".join(f"- {d['text']}" for d in decisions)
