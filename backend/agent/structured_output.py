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


def extract_json_object(text: str, validator: Callable[[dict], bool]) -> dict | None:
    cleaned = strip_reasoning(text)
    for candidate in reversed(_balanced_objects(cleaned)):
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict) and validator(value):
            return value
    return None
