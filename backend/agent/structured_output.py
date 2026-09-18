"""Small shared helpers for bounded prompts and strict JSON agent output."""

import json
from collections.abc import Callable

from .output_guard import strip_reasoning


def compact_json(value, max_chars: int = 5000) -> str:
    text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def compact_sources(results: list, limit: int = 6, snippet_chars: int = 220) -> list[dict]:
    sources = []
    for index, result in enumerate(results[:limit], start=1):
        sources.append(
            {
                "sourceId": f"src-{index}",
                "title": str(result.get("title", ""))[:160],
                "snippet": str(result.get("snippet", ""))[:snippet_chars],
                "url": str(result.get("url", "")),
                "angle": str(result.get("angle", "")),
                # None (not a guessed date) when the search provider this
                # result came from doesn't expose one - see tools.py.
                "publishedAt": result.get("publishedAt"),
            }
        )
    return sources


def _balanced_objects(text: str) -> list[str]:
    objects = []
    depth = 0
    start = None
    in_string = False
    escaped = False

    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])

    return objects


_JSON_LEGAL_ESCAPES = set('"\\/bfnrtu')


def _repair_invalid_escapes(text: str) -> str:
    """Repair invalid escape sequences some models emit inside JSON strings
    (e.g. writing an apostrophe as \\', which json.loads rejects outright).
    JSON only allows the escapes \\" \\\\ \\/ \\b \\f \\n \\r \\t and \\uXXXX,
    so a backslash before any other character is the model's own escaping
    slip rather than real JSON - dropping the backslash and keeping the
    character is a pure repair, never a content change. Already-valid
    escapes (including an escaped backslash) are preserved untouched.

    Confirmed live (Sept 15, 2026) against groq/qwen/qwen3.8-27b: inside
    JSON string values it wrote apostrophes with a backslash (don't as
    don\\'t), which threw away an otherwise valid, fully-grounded response
    on that artifact alone.
    """
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in _JSON_LEGAL_ESCAPES:
                out.append(ch)
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_json_object(text: str, validator: Callable[[dict], bool]) -> dict | None:
    """Try every balanced {...} substring in `text`, last-to-first, and
    return the first one that's both valid JSON and passes `validator`.
    Recovers the real answer even when the model buries it in a rambling
    scratchpad or wraps it in markdown, as long as it does eventually
    produce valid JSON somewhere.

    Each candidate gets two parse attempts - as-is, then after
    _repair_invalid_escapes - so a correct answer carrying a stray invalid
    escape still lands instead of being discarded wholesale.
    """
    cleaned = strip_reasoning(text)
    for candidate in reversed(_balanced_objects(cleaned)):
        for attempt_text in (candidate, _repair_invalid_escapes(candidate)):
            try:
                value = json.loads(attempt_text)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(value, dict) and validator(value):
                return value
    return None
