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

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="Affinity API")

# The same idea/target customer/problem gets resubmitted constantly during
# testing - each resubmission was burning real Groq quota for output that's
# already been generated once. In-memory is fine here: a single Render
# instance, and losing the cache on a restart just means the next identical
# request pays for itself again, not a correctness problem.
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
    return hashlib.sha256(normalized.encode()).hexdigest()


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
    _cache[key] = (time.time(), data)

frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class ValidateRequest(BaseModel):
    idea: str
    targetCustomer: str = ""
    problem: str = ""


@app.post("/validate")
def validate_idea(payload: ValidateRequest):
    if not payload.idea.strip():
        return JSONResponse(status_code=400, content={"error": "idea is required"})

    cache_key = _cache_key(payload)
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.info("Cache hit - skipping the pipeline for an identical request")
        return cached

    state = pipeline.invoke(
        {
            "idea": payload.idea,
            "targetCustomer": payload.targetCustomer,
            "problem": payload.problem,
        }
    )

    if state.get("error"):
        return JSONResponse(status_code=502, content={"error": state["error"]})

    response = {
        "summary": state["summary"],
        "results": state["results"],
        "marketOpportunity": state.get("marketOpportunity"),
        "competitors": state.get("competitors"),
        "errors": state.get("errors", {}),
    }

    # Only cache a genuinely complete result - caching a rate-limited partial
    # failure would lock a real, fixable problem in place for the full TTL
    # instead of letting the next attempt actually succeed once quota frees up.
    if not any(response["errors"].values()):
        _set_cached(cache_key, response)

    return response


@app.get("/health")
def health():
    return {"status": "ok"}
