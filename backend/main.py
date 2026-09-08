import hashlib
import json
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.graph import pipeline


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

    # ----------------------------------------------
    # Prepare response
    # ----------------------------------------------

    response = {
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