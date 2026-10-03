"""Per-report pipeline trace: which steps ran, how long each took, and which
model served it - the data behind the "how this report was made" view.

Steps are recorded by graph._timed and models by llm.py's success path. The
step being timed is held in a ContextVar (an object, so writes made inside a
worker thread that copied the context still land on it), and finished steps are
kept in a small in-memory registry keyed by the request, then taken out once by
the route that builds the response. Nothing here can fail a run: every public
function swallows its own errors.
"""

import contextvars
import hashlib
import threading
from collections import OrderedDict

_MAX_RUNS = 50

_current: contextvars.ContextVar = contextvars.ContextVar("pipeline_trace_step", default=None)
_runs: "OrderedDict[str, list]" = OrderedDict()
_lock = threading.Lock()


def run_key(idea, target_customer, problem) -> str:
    raw = "|".join(" ".join(str(x or "").lower().split()) for x in (idea, target_customer, problem))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def begin_step():
    """Start collecting model names for the step about to run; returns the token."""
    step = {"models": []}
    return _current.set(step), step


def end_step(token) -> None:
    try:
        _current.reset(token)
    except (ValueError, LookupError):
        pass


def note_model(model) -> None:
    try:
        step = _current.get()
        if step is not None and model and model not in step["models"]:
            step["models"].append(str(model))
    except Exception:
        pass


def record(key: str, node: str, seconds: float, models: list) -> None:
    try:
        with _lock:
            steps = _runs.setdefault(key, [])
            steps.append({"node": node, "seconds": round(float(seconds), 2), "models": list(models)})
            _runs.move_to_end(key)
            while len(_runs) > _MAX_RUNS:
                _runs.popitem(last=False)
    except Exception:
        pass


def take(key: str) -> list:
    """The steps recorded for a run (in the order they finished), removed from the registry."""
    try:
        with _lock:
            return _runs.pop(key, [])
    except Exception:
        return []
