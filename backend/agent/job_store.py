"""Bounded in-memory store for validation runs that outlive the initial
HTTP request (see main.py's async email-on-completion path).

Same shape/limits philosophy as session_store.py: a single-process,
in-memory dict is enough for this app's current scale, and TTL + a max
entry count keep it from growing unbounded across a long-running process.
This does not survive a restart and does not work across multiple backend
instances - documented in DEPLOYMENT.md alongside the same limitation for
chat sessions.
"""

import copy
import threading
import time
import uuid

_JOB_TTL_SECONDS = 2 * 60 * 60
_MAX_JOBS = 200

_lock = threading.RLock()
_jobs: dict[str, dict] = {}


def _prune(now: float) -> None:
    expired = [job_id for job_id, job in _jobs.items() if now - job["updatedAt"] > _JOB_TTL_SECONDS]
    for job_id in expired:
        del _jobs[job_id]

    if len(_jobs) > _MAX_JOBS:
        oldest = sorted(_jobs, key=lambda key: _jobs[key]["updatedAt"])
        for job_id in oldest[: len(_jobs) - _MAX_JOBS]:
            del _jobs[job_id]


def create_job() -> str:
    now = time.time()
    job_id = str(uuid.uuid4())
    with _lock:
        _prune(now)
        _jobs[job_id] = {
            "status": "processing",
            "result": None,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        }
    return job_id


def complete_job(job_id: str, result: dict) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job["status"] = "complete"
        job["result"] = result
        job["updatedAt"] = time.time()


def fail_job(job_id: str, error_message: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job["status"] = "failed"
        job["error"] = error_message
        job["updatedAt"] = time.time()


def get_job(job_id: str) -> dict | None:
    now = time.time()
    with _lock:
        _prune(now)
        job = _jobs.get(job_id)
        if job is None:
            return None
        return copy.deepcopy(job)


def clear_jobs() -> None:
    with _lock:
        _jobs.clear()
