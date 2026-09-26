import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.chat_graph import ChatRateLimitError, run_chat_turn
from agent.db import cache_table, get_engine
from agent.email_delivery import (
    is_valid_email,
    send_canonical_report_email,
    send_report_email,
)
from agent.graph import pipeline
from agent.job_store import complete_job, create_job, fail_job, get_job
from agent.pdf_exporter import generate_dossier_pdf
from agent.report_assembler import assemble_report, report_to_pdf_input
from agent.session_store import create_session, get_session
from agent.structured_output import compact_sources

from sqlalchemy import delete, select


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Affinity API",
    description="AI-Based Startup Idea Validator with Market Analysis",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

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


# ============================================================
# REQUEST TRACING
# ============================================================

@app.middleware("http")
async def _request_tracing_middleware(
    request: Request,
    call_next,
):
    request_id = uuid.uuid4().hex[:12]
    start = time.time()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request error | request_id=%s",
            request_id,
        )
        raise

    elapsed_ms = round(
        (time.time() - start) * 1000
    )

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request_id=%s method=%s path=%s status=%d elapsed_ms=%d",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )

    return response


# ============================================================
# CACHE
# ============================================================

_CACHE_TTL_SECONDS = 30 * 60

# ------------------------------------------------------------
# Cache can be controlled from .env
#
# During development/testing:
# VALIDATION_CACHE_ENABLED=false
#
# Production:
# VALIDATION_CACHE_ENABLED=true
# ------------------------------------------------------------

_CACHE_ENABLED = os.environ.get(
    "VALIDATION_CACHE_ENABLED",
    "false",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _cache_key(payload: "ValidateRequest") -> str:
    """
    Create a cache key using ALL validation inputs.

    This prevents requests with the same idea but different
    context from sharing old results.
    """

    normalized = json.dumps(
        {
            "idea": payload.idea.strip().lower(),
            "targetCustomer": payload.targetCustomer.strip().lower(),
            "problem": payload.problem.strip().lower(),
            "industry": payload.industry.strip().lower(),
            "location": payload.location.strip().lower(),
            "budget": payload.budget.strip().lower(),
            "stage": payload.stage.strip().lower(),
        },
        sort_keys=True,
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def _get_cached(key: str) -> dict | None:

    if not _CACHE_ENABLED:
        return None

    engine = get_engine()

    with engine.begin() as conn:

        row = conn.execute(
            select(cache_table).where(
                cache_table.c.cache_key == key
            )
        ).first()

        if row is None:
            return None

        if (
            time.time() - row.cached_at
            > _CACHE_TTL_SECONDS
        ):

            conn.execute(
                delete(cache_table).where(
                    cache_table.c.cache_key == key
                )
            )

            return None

        return row.data


def _set_cached(
    key: str,
    data: dict,
) -> None:

    if not _CACHE_ENABLED:
        return

    engine = get_engine()

    with engine.begin() as conn:

        conn.execute(
            delete(cache_table).where(
                cache_table.c.cache_key == key
            )
        )

        conn.execute(
            cache_table.insert().values(
                cache_key=key,
                data=data,
                cached_at=time.time(),
            )
        )


def _clear_cache() -> None:
    """
    Test-only helper.
    """

    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(
            delete(cache_table)
        )


# ============================================================
# RATE LIMITING
# ============================================================

_RATE_LIMIT_WINDOW_SECONDS = 60.0


_VALIDATE_RATE_LIMIT = int(
    os.environ.get(
        "VALIDATE_RATE_LIMIT_PER_MINUTE",
        "10",
    )
)


_CHAT_RATE_LIMIT = int(
    os.environ.get(
        "CHAT_RATE_LIMIT_PER_MINUTE",
        "30",
    )
)


_EXPORT_PDF_RATE_LIMIT = int(
    os.environ.get(
        "EXPORT_PDF_RATE_LIMIT_PER_MINUTE",
        "10",
    )
)


_REPORT_EMAIL_RATE_LIMIT = int(
    os.environ.get(
        "REPORT_EMAIL_RATE_LIMIT_PER_MINUTE",
        "5",
    )
)


_rate_limit_lock = threading.Lock()


_rate_limit_hits: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:

    return (
        request.client.host
        if request.client
        else "unknown"
    )


def _is_rate_limited(
    key: str,
    max_requests: int,
    window_seconds: float = _RATE_LIMIT_WINDOW_SECONDS,
) -> bool:

    now = time.time()

    cutoff = now - window_seconds

    with _rate_limit_lock:

        hits = [
            t
            for t in _rate_limit_hits.get(key, [])
            if t >= cutoff
        ]

        if len(hits) >= max_requests:

            _rate_limit_hits[key] = hits

            return True

        hits.append(now)

        _rate_limit_hits[key] = hits

        return False


def _rate_limit_response(
    retry_message: str,
) -> JSONResponse:

    return JSONResponse(
        status_code=429,
        content={
            "error": retry_message
        },
    )


def _clear_rate_limits() -> None:
    """
    Test-only helper.
    """

    with _rate_limit_lock:
        _rate_limit_hits.clear()


# ============================================================
# ASYNC / EMAIL DELIVERY
# ============================================================

_ASYNC_EMAIL_THRESHOLD_SECONDS = float(
    os.environ.get(
        "VALIDATE_ASYNC_THRESHOLD_SECONDS",
        "25",
    )
)


# ============================================================
# REQUEST MODELS
# ============================================================

class ValidateRequest(BaseModel):

    idea: str = Field(
        max_length=300,
    )

    targetCustomer: str = ""

    problem: str = ""

    industry: str = ""

    location: str = ""

    budget: str = ""

    stage: str = ""

    email: str = ""

    @field_validator("email")
    @classmethod
    def _validate_email(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if value and not is_valid_email(value):

            raise ValueError(
                "email must be a valid email address"
            )

        return value


class ChatRequest(BaseModel):

    sessionId: str = Field(
        min_length=1,
        max_length=64,
    )

    message: str = Field(
        min_length=1,
        max_length=1200,
    )


class PdfExportRequest(BaseModel):

    model_config = ConfigDict(
        extra="allow"
    )

    idea: str | None = None

    ideaTitle: str | None = None

    targetCustomer: str | None = None

    summary: str | None = None

    marketOpportunity: dict | None = None

    competitors: dict | None = None

    whiteSpace: dict | None = None

    swot: dict | None = None

    mvp: dict | None = None

    gtm: dict | None = None


class EmailReportRequest(BaseModel):

    recipient: str

    @field_validator("recipient")
    @classmethod
    def _validate_recipient(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value or not is_valid_email(value):

            raise ValueError(
                "recipient must be a valid email address"
            )

        return value


# ============================================================
# CREATE VALIDATION SESSION
# ============================================================

def _create_validation_session(
    payload: ValidateRequest,
    response: dict,
) -> str:

    return create_session(
        {
            "idea": payload.idea.strip(),

            "targetCustomer": (
                payload.targetCustomer.strip()
            ),

            "problem": (
                payload.problem.strip()
            ),

            "industry": (
                payload.industry.strip()
            ),

            "location": (
                payload.location.strip()
            ),

            "budget": (
                payload.budget.strip()
            ),

            "stage": (
                payload.stage.strip()
            ),

            "summary": response.get(
                "summary",
                "",
            ),

            "sources": compact_sources(
                response.get(
                    "results",
                    [],
                ),
                limit=8,
            ),

            "confidence": response.get(
                "confidence"
            ),

            "marketOpportunity": response.get(
                "marketOpportunity"
            ),

            "competitors": response.get(
                "competitors"
            ),

            "whiteSpace": response.get(
                "whiteSpace"
            ),

            "swot": response.get(
                "swot"
            ),

            "mvp": response.get(
                "mvp"
            ),

            "gtm": response.get(
                "gtm"
            ),

            "contradictions": response.get(
                "contradictions"
            ),

            "experiments": response.get(
                "experiments"
            ),

            "actionPlan": response.get(
                "actionPlan"
            ),
        }
    )


# ============================================================
# ROOT ROUTE
# ============================================================

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


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "Affinity API",
        "cache_enabled": _CACHE_ENABLED,
    }


# ============================================================
# PIPELINE ERROR
# ============================================================

class PipelineStateError(Exception):
    """
    Pipeline completed but recorded a hard failure.
    """

    pass


# ============================================================
# RUN PIPELINE
# ============================================================

def _run_pipeline_and_build_response(
    payload: ValidateRequest,
    cache_key: str,
) -> dict:

    logger.info(
        "Starting validation pipeline"
    )

    logger.info(
        "Pipeline input | industry=%s | location=%s | "
        "budget=%s | stage=%s",
        payload.industry,
        payload.location,
        payload.budget,
        payload.stage,
    )

    # --------------------------------------------------------
    # LangGraph / Validation Pipeline
    # --------------------------------------------------------

    state = pipeline.invoke(
        {
            "idea": payload.idea,

            "targetCustomer": (
                payload.targetCustomer
            ),

            "problem": (
                payload.problem
            ),

            "industry": (
                payload.industry
            ),

            "location": (
                payload.location
            ),

            "budget": (
                payload.budget
            ),

            "stage": (
                payload.stage
            ),
        }
    )

    # --------------------------------------------------------
    # Pipeline error
    # --------------------------------------------------------

    if state.get("error"):

        raise PipelineStateError(
            state["error"]
        )

    # --------------------------------------------------------
    # Build API response
    # --------------------------------------------------------

    response = {

        "summary": state.get(
            "summary",
            "",
        ),

        "results": state.get(
            "results",
            [],
        ),

        "confidence": state.get(
            "confidence"
        ),

        "marketOpportunity": state.get(
            "marketOpportunity"
        ),

        "competitors": state.get(
            "competitors"
        ),

        "whiteSpace": state.get(
            "whiteSpace"
        ),

        "swot": state.get(
            "swot"
        ),

        "mvp": state.get(
            "mvp"
        ),

        "gtm": state.get(
            "gtm"
        ),

        "contradictions": state.get(
            "contradictions"
        ),

        "errors": state.get(
            "errors",
            {},
        ),
    }

    # --------------------------------------------------------
    # Cache successful result
    # --------------------------------------------------------

    errors = response.get(
        "errors",
        {},
    )

    if not errors or not any(errors.values()):

        _set_cached(
            cache_key,
            response,
        )

        if _CACHE_ENABLED:

            logger.info(
                "Validation result cached"
            )

        else:

            logger.info(
                "Validation cache disabled - result not cached"
            )

    else:

        logger.warning(
            "Validation result contains errors - "
            "result will not be cached"
        )

    return response


# ============================================================
# ASYNC VALIDATION
# ============================================================

async def _finish_async_validation(
    task: "asyncio.Task[dict]",
    job_id: str,
    payload: ValidateRequest,
) -> None:

    try:

        response = await task

    except Exception as exc:

        logger.exception(
            "Async validation failed"
        )

        fail_job(
            job_id,
            str(exc),
        )

        return

    # --------------------------------------------------------
    # Create session
    # --------------------------------------------------------

    session_id = _create_validation_session(
        payload,
        response,
    )

    # --------------------------------------------------------
    # Complete job
    # --------------------------------------------------------

    complete_job(
        job_id,
        {
            **response,
            "sessionId": session_id,
        },
    )

    # --------------------------------------------------------
    # Email report
    # --------------------------------------------------------

    if payload.email:

        sent = send_report_email(
            payload.email,
            payload.idea,
            response,
        )

        if not sent:

            logger.warning(
                "Report email was not delivered for job %s",
                job_id,
            )


# ============================================================
# VALIDATE STARTUP IDEA
# ============================================================

@app.post("/validate")
async def validate_idea(
    payload: ValidateRequest,
    request: Request,
):

    # --------------------------------------------------------
    # Rate limit
    # --------------------------------------------------------

    if _is_rate_limited(
        f"validate:{_client_ip(request)}",
        _VALIDATE_RATE_LIMIT,
    ):

        return _rate_limit_response(
            "Too many validation requests. "
            "Please wait a minute and try again."
        )

    # --------------------------------------------------------
    # Input validation
    # --------------------------------------------------------

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

    logger.info(
        "Validation context | targetCustomer=%s | "
        "industry=%s | location=%s | budget=%s | stage=%s",
        payload.targetCustomer,
        payload.industry,
        payload.location,
        payload.budget,
        payload.stage,
    )

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    cache_key = _cache_key(
        payload
    )

    if _CACHE_ENABLED:

        cached = _get_cached(
            cache_key
        )

        if cached is not None:

            logger.info(
                "Cache hit - skipping pipeline"
            )

            session_id = _create_validation_session(
                payload,
                cached,
            )

            return {
                **cached,
                "sessionId": session_id,
            }

        logger.info(
            "Cache miss - running pipeline"
        )

    else:

        logger.info(
            "Validation cache disabled - "
            "running pipeline"
        )

    # --------------------------------------------------------
    # Pipeline
    # --------------------------------------------------------

    task = asyncio.create_task(
        asyncio.to_thread(
            _run_pipeline_and_build_response,
            payload,
            cache_key,
        )
    )

    # --------------------------------------------------------
    # Async email mode
    # --------------------------------------------------------

    if payload.email:

        done, _pending = await asyncio.wait(
            {task},
            timeout=_ASYNC_EMAIL_THRESHOLD_SECONDS,
        )

        if task not in done:

            job_id = create_job()

            asyncio.create_task(
                _finish_async_validation(
                    task,
                    job_id,
                    payload,
                )
            )

            return JSONResponse(
                status_code=202,
                content={
                    "status": "processing",
                    "jobId": job_id,
                    "message": (
                        "This is taking longer than usual. "
                        "We'll email your report to "
                        f"{payload.email} as soon as it's ready."
                    ),
                },
            )

    # --------------------------------------------------------
    # Get pipeline result
    # --------------------------------------------------------

    try:

        response = await task

    except PipelineStateError as exc:

        logger.error(
            "Pipeline state error: %s",
            exc,
        )

        return JSONResponse(
            status_code=502,
            content={
                "error": str(exc)
            },
        )

    except Exception as exc:

        logger.exception(
            "Pipeline execution failed"
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc)
            },
        )

    # --------------------------------------------------------
    # Session
    # --------------------------------------------------------

    session_id = _create_validation_session(
        payload,
        response,
    )

    return {
        **response,
        "sessionId": session_id,
    }


# ============================================================
# VALIDATION JOB STATUS
# ============================================================

@app.get("/validate/status/{job_id}")
def validate_status(
    job_id: str,
):

    job = get_job(
        job_id
    )

    if job is None:

        return JSONResponse(
            status_code=404,
            content={
                "error": "Job not found or expired."
            },
        )

    if job["status"] == "processing":

        return {
            "status": "processing"
        }

    if job["status"] == "failed":

        return JSONResponse(
            status_code=502,
            content={
                "status": "failed",
                "error": job["error"],
            },
        )

    return {
        "status": "complete",
        **job["result"],
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
def chat(
    payload: ChatRequest,
    request: Request,
):

    session_id = payload.sessionId.strip()

    message = payload.message.strip()

    if not session_id or not message:

        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "sessionId and message are required"
                )
            },
        )

    # --------------------------------------------------------
    # Rate limit
    # --------------------------------------------------------

    if _is_rate_limited(
        f"chat:{_client_ip(request)}",
        _CHAT_RATE_LIMIT,
    ):

        return _rate_limit_response(
            "Too many advisor messages. "
            "Please wait a minute and try again."
        )

    # --------------------------------------------------------
    # Chat
    # --------------------------------------------------------

    try:

        reply = run_chat_turn(
            session_id,
            message,
        )

    except KeyError:

        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    "Validation session not found or expired. "
                    "Run validation again."
                )
            },
        )

    except ChatRateLimitError:

        return JSONResponse(
            status_code=429,
            content={
                "error": (
                    "Too many advisor messages. "
                    "Please wait a minute and try again."
                )
            },
        )

    except ValueError as exc:

        return JSONResponse(
            status_code=400,
            content={
                "error": str(exc)
            },
        )

    except Exception:

        logger.exception(
            "Chat turn failed"
        )

        return JSONResponse(
            status_code=502,
            content={
                "error": (
                    "The advisor could not answer right now. "
                    "Please try again."
                )
            },
        )

    return {
        "reply": reply
    }


# ============================================================
# PDF EXPORT
# ============================================================

@app.post("/export-pdf")
def export_pdf_post(
    payload: PdfExportRequest,
    request: Request,
):

    if _is_rate_limited(
        f"export-pdf:{_client_ip(request)}",
        _EXPORT_PDF_RATE_LIMIT,
    ):

        return _rate_limit_response(
            "Too many PDF export requests. "
            "Please wait a minute and try again."
        )

    try:

        pdf_bytes = generate_dossier_pdf(
            payload.model_dump()
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    'attachment; filename="Affinity_Validation_Report.pdf"'
                )
            },
        )

    except Exception as exc:

        logger.exception(
            "PDF generation failed"
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": (
                    f"PDF export failed: {str(exc)}"
                )
            },
        )


# ============================================================
# PDF FROM SESSION
# ============================================================

@app.get("/validate/{session_id}/pdf")
def export_pdf_session(
    session_id: str,
    request: Request,
):

    if _is_rate_limited(
        f"export-pdf:{_client_ip(request)}",
        _EXPORT_PDF_RATE_LIMIT,
    ):

        return _rate_limit_response(
            "Too many PDF export requests. "
            "Please wait a minute and try again."
        )

    session = get_session(
        session_id
    )

    if not session:

        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    "Session not found or expired."
                )
            },
        )

    try:

        pdf_bytes = generate_dossier_pdf(
            session["context"]
        )

        filename = (
            f"Affinity_Report_{session_id}.pdf"
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{filename}"'
                )
            },
        )

    except Exception as exc:

        logger.exception(
            "PDF generation failed for session %s",
            session_id,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": (
                    f"PDF export failed: {str(exc)}"
                )
            },
        )


# ============================================================
# CANONICAL REPORT
# ============================================================

@app.get("/reports/{session_id}")
def get_report(
    session_id: str,
    request: Request,
):

    if _is_rate_limited(
        f"reports:{_client_ip(request)}",
        _EXPORT_PDF_RATE_LIMIT,
    ):

        return _rate_limit_response(
            "Too many report requests. "
            "Please wait a minute and try again."
        )

    session = get_session(
        session_id
    )

    if not session:

        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    "Session not found or expired."
                )
            },
        )

    return assemble_report(
        session_id,
        session["context"],
    )


# ============================================================
# EMAIL REPORT
# ============================================================

@app.post("/reports/{session_id}/email")
def email_report(
    session_id: str,
    payload: EmailReportRequest,
    request: Request,
):

    if _is_rate_limited(
        f"report-email:{_client_ip(request)}",
        _REPORT_EMAIL_RATE_LIMIT,
    ):

        return _rate_limit_response(
            "Too many email requests. "
            "Please wait a minute and try again."
        )

    session = get_session(
        session_id
    )

    if not session:

        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    "Session not found or expired."
                )
            },
        )

    report = assemble_report(
        session_id,
        session["context"],
    )

    try:

        pdf_bytes = generate_dossier_pdf(
            report_to_pdf_input(report)
        )

    except Exception:

        logger.exception(
            "PDF generation failed while emailing "
            "report for session %s",
            session_id,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": (
                    "Could not generate the report PDF "
                    "for delivery."
                )
            },
        )

    delivery_id = str(
        uuid.uuid4()
    )

    sent = send_canonical_report_email(
        payload.recipient,
        report,
        pdf_bytes,
    )

    if not sent:

        return JSONResponse(
            status_code=502,
            content={
                "status": "failed",
                "error": (
                    "Email delivery is not available "
                    "right now. Please try again shortly."
                ),
            },
        )

    return JSONResponse(
        status_code=202,
        content={
            "status": "queued",
            "deliveryId": delivery_id,
        },
    )


# ============================================================
# START UVICORN SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )