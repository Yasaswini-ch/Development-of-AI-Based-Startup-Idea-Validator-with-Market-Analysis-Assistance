import asyncio
import hashlib
import json
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from agent.chat_graph import ChatRateLimitError, run_chat_turn
from agent.email_delivery import is_valid_email, send_report_email
from agent.graph import pipeline
from agent.job_store import complete_job, create_job, fail_job, get_job
from agent.pdf_exporter import generate_dossier_pdf
from agent.session_store import create_session, get_session
from agent.structured_output import compact_sources


# --------------------------------------------------
# ENVIRONMENT
# --------------------------------------------------

load_dotenv()


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# FASTAPI APP
# --------------------------------------------------

app = FastAPI(
    title="Affinity API",
    description="AI-Based Startup Idea Validator with Market Analysis",
    version="1.0.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

frontend_origin = os.environ.get(
    "FRONTEND_ORIGIN",
    "http://localhost:5173",
)
allowed_origins = {
    frontend_origin.rstrip("/"),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# CACHE
# --------------------------------------------------

_CACHE_TTL_SECONDS = 30 * 60

_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(payload: "ValidateRequest") -> str:
    normalized = json.dumps(
        {
            "idea": payload.idea.strip().lower(),
            "targetCustomer": payload.targetCustomer.strip().lower(),
            "problem": payload.problem.strip().lower(),
        },
        sort_keys=True,
    )

    return hashlib.sha256(
        normalized.encode()
    ).hexdigest()


def _get_cached(key: str) -> dict | None:
    entry = _cache.get(key)

    if entry is None:
        return None

    cached_at, data = entry

    if time.time() - cached_at > _CACHE_TTL_SECONDS:
        del _cache[key]
        return None

    return data


def _set_cached(key: str, data: dict) -> None:
    _cache[key] = (
        time.time(),
        data,
    )


# --------------------------------------------------
# ASYNC / EMAIL DELIVERY
# --------------------------------------------------

# If a caller supplies an email and the pipeline is still running past this
# threshold, /validate returns immediately with a "processing" response
# instead of holding the HTTP connection open, and emails the report when
# the (still-running) pipeline finishes. Callers that don't supply an email
# keep the original fully-synchronous behavior unchanged.
_ASYNC_EMAIL_THRESHOLD_SECONDS = float(os.environ.get("VALIDATE_ASYNC_THRESHOLD_SECONDS", "25"))


# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------

class ValidateRequest(BaseModel):
    idea: str
    targetCustomer: str = ""
    problem: str = ""
    email: str = ""

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip()
        if value and not is_valid_email(value):
            raise ValueError("email must be a valid email address")
        return value


class ChatRequest(BaseModel):
    sessionId: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1200)


def _create_validation_session(payload: ValidateRequest, response: dict) -> str:
    return create_session(
        {
            "idea": payload.idea.strip(),
            "targetCustomer": payload.targetCustomer.strip(),
            "problem": payload.problem.strip(),
            "summary": response.get("summary", ""),
            "sources": compact_sources(response.get("results", []), limit=8),
            "confidence": response.get("confidence"),
            "marketOpportunity": response.get("marketOpportunity"),
            "competitors": response.get("competitors"),
            "whiteSpace": response.get("whiteSpace"),
            "swot": response.get("swot"),
            "mvp": response.get("mvp"),
            "gtm": response.get("gtm"),
        }
    )


# --------------------------------------------------
# ROOT ROUTE
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Affinity API is running",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "validate_endpoint": "/validate",
        "chat_endpoint": "/chat",
        "pdf_export_endpoint": "/export-pdf",
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Affinity API",
    }


class PipelineStateError(Exception):
    """The pipeline completed but recorded a hard failure in state['error']
    (e.g. every search source failed for every angle) - a 502 to the
    caller, distinct from an unexpected exception (500). See
    docs/architecture.md's documented /validate error contract.
    """


def _run_pipeline_and_build_response(payload: ValidateRequest, cache_key: str) -> dict:
    """Runs the full LangGraph pipeline and returns the same response shape
    /validate has always returned (minus sessionId, added by the caller).
    Raises PipelineStateError for a recorded pipeline-state failure, or the
    original exception for anything unexpected - the caller decides how to
    report either, depending on whether it's still inside the synchronous
    request/response cycle or already running in the background for the
    async/email path.
    """
    state = pipeline.invoke(
        {
            "idea": payload.idea,
            "targetCustomer": payload.targetCustomer,
            "problem": payload.problem,
        }
    )

    if state.get("error"):
        raise PipelineStateError(state["error"])

    response = {
        "summary": state.get("summary", ""),
        "results": state.get("results", []),
        # Sashi's Cross-Source Confidence
        "confidence": state.get("confidence"),
        # Sashi's Opportunity Score is attached inside marketOpportunity
        "marketOpportunity": state.get("marketOpportunity"),
        "competitors": state.get("competitors"),
        "whiteSpace": state.get("whiteSpace"),
        "swot": state.get("swot"),
        "mvp": state.get("mvp"),
        "gtm": state.get("gtm"),
        "errors": state.get("errors", {}),
    }

    if not any(response["errors"].values()):
        _set_cached(cache_key, response)
        logger.info("Validation result cached")

    return response


async def _finish_async_validation(task: "asyncio.Task[dict]", job_id: str, payload: ValidateRequest) -> None:
    """Awaits the still-running pipeline task after /validate has already
    responded with a "processing" status, stores the outcome in the job
    store for polling, and emails the report on success. Runs as a detached
    background task - see the /validate handler.
    """
    try:
        response = await task
    except Exception as exc:
        logger.exception("Async validation failed")
        fail_job(job_id, str(exc))
        return

    session_id = _create_validation_session(payload, response)
    complete_job(job_id, {**response, "sessionId": session_id})

    if payload.email:
        sent = send_report_email(payload.email, payload.idea, response)
        if not sent:
            logger.warning("Report email was not delivered for job %s", job_id)


# --------------------------------------------------
# VALIDATE STARTUP IDEA
# --------------------------------------------------

@app.post("/validate")
async def validate_idea(payload: ValidateRequest):

    # ----------------------------------------------
    # Validate input
    # ----------------------------------------------

    if not payload.idea.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": "idea is required"
            },
        )

    logger.info(
        "Validation request received: %s",
        payload.idea,
    )

    # ----------------------------------------------
    # Check cache
    # ----------------------------------------------

    cache_key = _cache_key(payload)

    cached = _get_cached(cache_key)

    if cached is not None:

        logger.info(
            "Cache hit - skipping pipeline"
        )

        session_id = _create_validation_session(payload, cached)
        return {**cached, "sessionId": session_id}

    # ----------------------------------------------
    # Run LangGraph pipeline (in a worker thread - it's synchronous,
    # CPU/IO-bound crew + search work)
    # ----------------------------------------------

    task = asyncio.create_task(
        asyncio.to_thread(_run_pipeline_and_build_response, payload, cache_key)
    )

    if payload.email:
        # asyncio.wait (unlike wait_for) does not cancel the task on
        # timeout, so the pipeline keeps running in the background if it's
        # not done in time - that's the whole point of this path.
        done, _pending = await asyncio.wait({task}, timeout=_ASYNC_EMAIL_THRESHOLD_SECONDS)

        if task not in done:
            job_id = create_job()
            asyncio.create_task(_finish_async_validation(task, job_id, payload))
            return JSONResponse(
                status_code=202,
                content={
                    "status": "processing",
                    "jobId": job_id,
                    "message": (
                        "This is taking longer than usual. We'll email your report to "
                        f"{payload.email} as soon as it's ready."
                    ),
                },
            )

    try:
        response = await task
    except PipelineStateError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": str(exc)},
        )
    except Exception as exc:
        logger.exception("Pipeline execution failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    # ----------------------------------------------
    # Return response
    # ----------------------------------------------

    session_id = _create_validation_session(payload, response)
    return {**response, "sessionId": session_id}


# --------------------------------------------------
# POLL AN ASYNC VALIDATION JOB
# --------------------------------------------------

@app.get("/validate/status/{job_id}")
def validate_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Job not found or expired."},
        )

    if job["status"] == "processing":
        return {"status": "processing"}

    if job["status"] == "failed":
        return JSONResponse(
            status_code=502,
            content={"status": "failed", "error": job["error"]},
        )

    return {"status": "complete", **job["result"]}


# --------------------------------------------------
# CONVERSATIONAL STARTUP ADVISOR
# --------------------------------------------------

@app.post("/chat")
def chat(payload: ChatRequest):
    session_id = payload.sessionId.strip()
    message = payload.message.strip()

    if not session_id or not message:
        return JSONResponse(
            status_code=400,
            content={"error": "sessionId and message are required"},
        )

    try:
        reply = run_chat_turn(session_id, message)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"error": "Validation session not found or expired. Run validation again."},
        )
    except ChatRateLimitError:
        return JSONResponse(
            status_code=429,
            content={"error": "Too many advisor messages. Please wait a minute and try again."},
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )
    except Exception:
        logger.exception("Chat turn failed")
        return JSONResponse(
            status_code=502,
            content={"error": "The advisor could not answer right now. Please try again."},
        )

    return {"reply": reply}


# --------------------------------------------------
# AUTOMATED PDF REPORT EXPORTER
# --------------------------------------------------

@app.post("/export-pdf")
def export_pdf_post(payload: dict):
    """Compile a validation response payload (already fetched by the
    frontend) into a downloadable PDF report."""
    try:
        pdf_bytes = generate_dossier_pdf(payload)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="Affinity_Validation_Report.pdf"'
            },
        )
    except Exception as exc:
        logger.exception("PDF generation failed")
        return JSONResponse(
            status_code=500,
            content={"error": f"PDF export failed: {str(exc)}"},
        )


@app.get("/validate/{session_id}/pdf")
def export_pdf_session(session_id: str):
    """Generate a PDF report from an existing validation session's stored
    context (see session_store.create_session)."""
    session = get_session(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found or expired."},
        )

    try:
        pdf_bytes = generate_dossier_pdf(session["context"])
        filename = f"Affinity_Report_{session_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.exception("PDF generation failed for session %s", session_id)
        return JSONResponse(
            status_code=500,
            content={"error": f"PDF export failed: {str(exc)}"},
        )
