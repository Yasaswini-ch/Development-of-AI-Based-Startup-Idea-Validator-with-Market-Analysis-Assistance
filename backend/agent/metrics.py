"""In-process counters for the metrics docs/api-cost-accuracy-performance-metrics.md's
own §7 (Open Metrics) flagged as "not yet measured": cache hit rate and
per-node LLM success/failure counts. Intentionally simple - a thread-safe
in-memory counter, not a DB-backed table like session_store.py/job_store.py.
Those moved to the DB because losing a session or job on restart breaks a
user's in-flight request; losing a counter on restart just resets a
dashboard back to zero, which is an acceptable trade for not adding a
migration for pure observability.
"""

import threading
from collections import defaultdict

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)


def increment(key: str) -> None:
    with _lock:
        _counters[key] += 1


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def reset() -> None:
    """Test-only - production has no reason to reset counters mid-process."""
    with _lock:
        _counters.clear()
