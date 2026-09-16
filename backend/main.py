import hashlib
import json
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from agent.chat_agent import advisor_respond
from agent.graph import pipeline
from agent.pdf_exporter import generate_dossier_pdf
from agent.session_store import create_session, get_session


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
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
# REQUEST MODEL
# --------------------------------------------------

class ValidateRequest(BaseModel):
    idea: str
    targetCustomer: str = ""
    problem: str = ""


class ChatRequest(BaseModel):
    sessionId: str
    message: str


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


# --------------------------------------------------
# VALIDATE STARTUP IDEA
# --------------------------------------------------

@app.post("/validate")
def validate_idea(payload: ValidateRequest):

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

        return cached

    # ----------------------------------------------
    # Run LangGraph pipeline
    # ----------------------------------------------

    try:

        state = pipeline.invoke(
            {
                "idea": payload.idea,
                "targetCustomer": payload.targetCustomer,
                "problem": payload.problem,
            }
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

    # ----------------------------------------------
    # Pipeline error
    # ----------------------------------------------

    if state.get("error"):

        return JSONResponse(
            status_code=502,
            content={
                "error": state["error"]
            },
        )

    # Milestone 3: Create Session ID
    session_id = create_session(state)

    response = {
        "sessionId": session_id,

        "summary": state.get(
            "summary",
            "",
        ),

        "results": state.get(
            "results",
            [],
        ),

        # Sashi's Cross-Source Confidence
        "confidence": state.get(
            "confidence"
        ),

        # Sashi's Opportunity Score is attached
        # inside marketOpportunity
        "marketOpportunity": state.get(
            "marketOpportunity"
        ),

        "competitors": state.get(
            "competitors"
        ),

        "whiteSpace": state.get(
            "whiteSpace"
        ),

        # Milestone 3 additions
        "swot": state.get("swot"),
        "mvp": state.get("mvp"),
        "gtm": state.get("gtm"),

        "errors": state.get(
            "errors",
            {},
        ),
    }

    # ----------------------------------------------
    # Cache only complete responses
    # ----------------------------------------------

    errors = response.get(
        "errors",
        {},
    )

    if not any(errors.values()):

        _set_cached(
            cache_key,
            response,
        )

        logger.info(
            "Validation result cached"
        )

    # ----------------------------------------------
    # Return response
    # ----------------------------------------------

    return response


# --------------------------------------------------
# MILESTONE 3: CONVERSATIONAL ADVISOR CHAT
# --------------------------------------------------

@app.post("/chat")
def chat_turn(payload: ChatRequest):
    if not payload.sessionId.strip() or not payload.message.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "sessionId and message are required."},
        )

    logger.info("Chat request for session %s: %s", payload.sessionId, payload.message[:40])

    res = advisor_respond(payload.sessionId, payload.message)

    if res.get("error"):
        return JSONResponse(
            status_code=404,
            content={"error": res["error"]},
        )

    return res


# --------------------------------------------------
# MILESTONE 3: AUTOMATED PDF REPORT EXPORTER
# --------------------------------------------------

@app.post("/export-pdf")
def export_pdf_post(payload: dict):
    """Compile validation payload into a downloadable PDF report."""
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
    """Generate PDF report from a active sessionId."""
    session_data = get_session(session_id)
    if not session_data:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found or expired."},
        )

    try:
        pdf_bytes = generate_dossier_pdf(session_data)
        filename = f"Affinity_Report_{session_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )
    except Exception as exc:
        logger.exception("PDF generation failed for session %s", session_id)
        return JSONResponse(
            status_code=500,
            content={"error": f"PDF export failed: {str(exc)}"},
        )