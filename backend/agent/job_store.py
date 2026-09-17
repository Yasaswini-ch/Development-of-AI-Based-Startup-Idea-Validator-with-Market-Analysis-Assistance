"""Database-backed store for validation runs that outlive the initial HTTP
request (see main.py's async email-on-completion path).

Same TTL + max-row-count pruning philosophy the in-memory version used, and
the same public interface (create_job/complete_job/fail_job/get_job/
clear_jobs), now backed by db.py's `jobs` table instead of a process-local
dict - it survives a restart and is visible across every backend instance,
which the previous in-memory version documented as a known limitation
(see DEPLOYMENT.md) and could not do.
"""

import uuid

from sqlalchemy import delete, select

from .db import get_engine, jobs_table, now

_JOB_TTL_SECONDS = 2 * 60 * 60
_MAX_JOBS = 200


def _prune(conn) -> None:
    cutoff = now() - _JOB_TTL_SECONDS
    conn.execute(delete(jobs_table).where(jobs_table.c.updated_at < cutoff))

    overflow = conn.execute(select(jobs_table.c.id).order_by(jobs_table.c.updated_at.desc())).scalars().all()
    if len(overflow) > _MAX_JOBS:
        stale_ids = overflow[_MAX_JOBS:]
        conn.execute(delete(jobs_table).where(jobs_table.c.id.in_(stale_ids)))


def create_job() -> str:
    job_id = str(uuid.uuid4())
    timestamp = now()
    engine = get_engine()
    with engine.begin() as conn:
        _prune(conn)
        conn.execute(
            jobs_table.insert().values(
                id=job_id,
                status="processing",
                result=None,
                error=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return job_id


def complete_job(job_id: str, result: dict) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            jobs_table.update()
            .where(jobs_table.c.id == job_id)
            .values(status="complete", result=result, updated_at=now())
        )


def fail_job(job_id: str, error_message: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            jobs_table.update()
            .where(jobs_table.c.id == job_id)
            .values(status="failed", error=error_message, updated_at=now())
        )


def get_job(job_id: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        _prune(conn)
        row = conn.execute(select(jobs_table).where(jobs_table.c.id == job_id)).first()
        if row is None:
            return None
        return {
            "status": row.status,
            "result": row.result,
            "error": row.error,
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
        }


def clear_jobs() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(jobs_table))
