import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid

from dotenv import load_dotenv

# --------------------------------------------------
# ENVIRONMENT
# --------------------------------------------------

# Must run before any `agent.*` import below - those transitively import
# crewai/litellm, which read provider API keys (GROQ_API_KEY etc.) from
# os.environ at import time in places.
#
# Explicit path, not load_dotenv()'s default upward search from the
# process's CWD - confirmed live that this matters: launched with a CWD
# other than backend/ (e.g. `uvicorn --app-dir backend main:app` run from
# the project root, which only adds backend/ to sys.path, not CWD),
# find_dotenv()'s search never reaches backend/.env at all, so a freshly
# updated key there was silently never loaded - GROQ_API_KEY stayed
# whatever the parent process's environment already had (usually unset),
# and every call failed with Groq's own "Invalid API Key" response,
# indistinguishable from a genuinely bad key. The same key, loaded
# explicitly from this exact path in isolation, worked immediately.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent import events, metrics
from agent.auth import (
    AuthError,
    is_admin,
    account_profile,
    login as auth_login,
    login_with_google as auth_login_with_google,
    optional_user,
    require_admin,
    request_password_reset,
    require_user,
    reset_password as auth_reset_password,
    signup as auth_signup,
)
from agent.google_auth import GoogleAuthError
from agent.chat_graph import ChatRateLimitError, classify_section, run_chat_turn
from agent.db import cache_table, database_backend, get_engine
from agent.email_delivery import (
    is_valid_email,
    send_canonical_report_email,
    send_password_reset_email,
    send_report_email,
)
from agent.graph import NEEDS_DEEP_ANALYSIS, pipeline
from agent.idea_category import categorize_idea
from agent.job_store import complete_job, create_job, fail_job, get_job
from agent.llm import local_llm_available
from agent.pdf_exporter import generate_dossier_pdf
from agent.platform_metrics import get_platform_metrics
from agent.report_assembler import assemble_report, report_to_pdf_input
from agent.session_store import claim_session, create_session, get_session, list_sessions_for_user
from agent.structured_output import compact_sources
from agent.user_analytics import get_user_analytics
from sqlalchemy import delete, select


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

def _report_url(session_id: str) -> str:
    """Link back to a past session for the "view this report again" email
    button - the closest thing to history without a real login system (see
    email_delivery.py's docstrings). Query-param based (?session=...), not
    a /reports/{id} frontend route, since the SPA has no client-side router.
    """
    return f"{frontend_origin.rstrip('/')}/?session={session_id}"


app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST TRACING
# --------------------------------------------------
#
# Every request gets a short id that's threaded through this one log line
# and echoed back as X-Request-ID, so a single request's node-by-node log
# lines (graph.py logs elapsed_ms per node - see confidence_dashboard_node
# and friends) can actually be correlated with the request that produced
# them, and with whatever the frontend/caller saw. Previously there was no
# way to tell which log lines belonged to which request at all.

@app.middleware("http")
async def _request_tracing_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    start = time.time()
    response = await call_next(request)
    elapsed_ms = round((time.time() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%d elapsed_ms=%d",
        request_id, request.method, request.url.path, response.status_code, elapsed_ms,
    )
    return response


# --------------------------------------------------
# CACHE
# --------------------------------------------------
#
# Backed by db.py's `validation_cache` table (Postgres in production,
# SQLite locally) instead of a process-local dict, so a cache hit survives
# a restart and is shared across however many backend instances are
# running - a repeated identical submission doesn't re-run the pipeline
# just because it landed on a different instance than the first request.

_CACHE_TTL_SECONDS = 30 * 60


def _cache_key(payload: "ValidateRequest") -> str:
    normalized = json.dumps(
        {
            "idea": payload.idea.strip().lower(),
            "targetCustomer": payload.targetCustomer.strip().lower(),
            "problem": payload.problem.strip().lower(),
            # Included so a "quick" response is never served for a "deep"
            # request or vice versa - otherwise identical idea/targetCustomer/
            # problem across two different mode requests would collide on
            # the same cache key and hand back the wrong shape of report.
            "mode": payload.mode,
        },
        sort_keys=True,
    )

    return hashlib.sha256(
        normalized.encode()
    ).hexdigest()


def _get_cached(key: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(cache_table).where(cache_table.c.cache_key == key)).first()

        if row is None:
            return None

        if time.time() - row.cached_at > _CACHE_TTL_SECONDS:
            conn.execute(delete(cache_table).where(cache_table.c.cache_key == key))
            return None

        return row.data


def _set_cached(key: str, data: dict) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(cache_table).where(cache_table.c.cache_key == key))
        conn.execute(cache_table.insert().values(cache_key=key, data=data, cached_at=time.time()))


def _clear_cache() -> None:
    """Test-only helper - mirrors the old dict's `.clear()` that
    test_milestone3.py's setUp relied on."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(cache_table))


# --------------------------------------------------
# RATE LIMITING
# --------------------------------------------------
#
# A per-IP sliding-window limiter in front of every expensive or abusable
# endpoint. /chat already had a per-session cap (session_store.py's
# reserve_chat_request) but nothing stopped a caller from just minting a
# fresh session per request - this closes that gap, and gives /validate and
# /export-pdf a limit they had none of before. Deliberately in-memory rather
# than DB-backed: a reset on restart (falling back to nothing-blocked) is an
# acceptable trade-off for a counter that only needs to survive minutes, not
# the durability sessions/jobs/cache actually needed.

_RATE_LIMIT_WINDOW_SECONDS = 60.0
_VALIDATE_RATE_LIMIT = int(os.environ.get("VALIDATE_RATE_LIMIT_PER_MINUTE", "10"))
_CHAT_RATE_LIMIT = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "30"))
_EXPORT_PDF_RATE_LIMIT = int(os.environ.get("EXPORT_PDF_RATE_LIMIT_PER_MINUTE", "10"))
_REPORT_EMAIL_RATE_LIMIT = int(os.environ.get("REPORT_EMAIL_RATE_LIMIT_PER_MINUTE", "5"))
# Tighter than the other limits on purpose - signup/login are the one pair
# of endpoints where the request itself (repeated password guesses) is the
# abuse, not just request volume.
_AUTH_RATE_LIMIT = int(os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE", "8"))

_rate_limit_lock = threading.Lock()
_rate_limit_hits: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_rate_limited(key: str, max_requests: int, window_seconds: float = _RATE_LIMIT_WINDOW_SECONDS) -> bool:
    now = time.time()
    cutoff = now - window_seconds
    with _rate_limit_lock:
        hits = [t for t in _rate_limit_hits.get(key, []) if t >= cutoff]
        if len(hits) >= max_requests:
            _rate_limit_hits[key] = hits
            return True
        hits.append(now)
        _rate_limit_hits[key] = hits
        return False


def _rate_limit_response(retry_message: str) -> JSONResponse:
    return JSONResponse(status_code=429, content={"error": retry_message})


def _clear_rate_limits() -> None:
    """Test-only helper - without this, every test in the same process
    shares the same in-memory rate-limit buckets (TestClient always uses
    the same fake client IP), so an unrelated earlier test's /validate
    calls could tip a later test over the limit."""
    with _rate_limit_lock:
        _rate_limit_hits.clear()


# --------------------------------------------------
# ASYNC / EMAIL DELIVERY
# --------------------------------------------------

# If a caller supplies an email and the pipeline is still running past this
# threshold, /validate returns immediately with a "processing" response
# instead of holding the HTTP connection open, and emails the report when
# the (still-running) pipeline finishes. Callers that don't supply an email
# keep the original fully-synchronous behavior unchanged.
_ASYNC_EMAIL_THRESHOLD_SECONDS = float(os.environ.get("VALIDATE_ASYNC_THRESHOLD_SECONDS", "60"))

# Sections that can independently degrade to a deterministic fallback or
# fail outright - same set report_assembler.py's _degraded_sections/
# _section_errors track for the canonical report, mirrored here since the
# raw /validate response uses the same top-level key names but isn't
# itself the canonical report shape.
_DEGRADABLE_SECTIONS = ("marketOpportunity", "competitors", "whiteSpace", "swot", "mvp", "gtm")


def _response_is_partial(response: dict) -> bool:
    """True if any section failed outright (errors.<section> set) or fell
    back to a deterministic result (degraded: true) - used to email the
    report even on a fast (<60s) response, since "fast but partial" is
    still worth flagging to someone who asked to be emailed, not just
    "slow." Never true for a fully clean response.
    """
    if any((response.get("errors") or {}).values()):
        return True
    return any(
        isinstance(response.get(section), dict) and response[section].get("degraded")
        for section in _DEGRADABLE_SECTIONS
    )


# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------

class SignupRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip()
        if not value or not is_valid_email(value):
            raise ValueError("email must be a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(max_length=200)


class GoogleAuthRequest(BaseModel):
    # The raw signed JWT Google's Identity Services button hands the
    # frontend - never the claims inside it, which the client could have
    # read but not forged. agent/google_auth.py re-verifies the signature
    # and audience server-side before trusting anything in it.
    idToken: str


class ClaimSessionRequest(BaseModel):
    sessionId: str = Field(min_length=1, max_length=64)


class ValidateRequest(BaseModel):
    idea: str = Field(max_length=2500)
    targetCustomer: str = Field(default="", max_length=600)
    problem: str = Field(default="", max_length=1500)
    email: str = ""
    # Track G.2 - "quick" runs only market/competitor/white-space analysis
    # (no SWOT/MVP/GTM/contradictions/experiments/action-plan); "deep" is
    # the full pipeline, unchanged default behavior.
    mode: str = "deep"

    @field_validator("idea")
    @classmethod
    def _validate_idea(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idea must not be empty or blank")
        return value

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip()
        if value and not is_valid_email(value):
            raise ValueError("email must be a valid email address")
        return value

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        value = value.strip().lower() or "deep"
        if value not in ("quick", "deep"):
            raise ValueError('mode must be "quick" or "deep"')
        return value


class ChatRequest(BaseModel):
    sessionId: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1200)


class PdfExportRequest(BaseModel):
    """Schema for POST /export-pdf. Previously accepted a raw `dict` with no
    validation at all - pdf_exporter.generate_dossier_pdf() reads every
    field defensively with .get(), so this only needs to catch a caller
    sending the wrong shape entirely (e.g. a list, or a string where a dict
    belongs) before it ever reaches ReportLab. `extra="allow"` because a
    caller may pass through the full /validate response body verbatim,
    including fields (results, errors, sessionId, ...) this exporter never
    reads.
    """

    model_config = ConfigDict(extra="allow")

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
    """Schema for POST /reports/{sessionId}/email (docs/unique-features-plan.md §7)."""

    recipient: str

    @field_validator("recipient")
    @classmethod
    def _validate_recipient(cls, value: str) -> str:
        value = value.strip()
        if not value or not is_valid_email(value):
            raise ValueError("recipient must be a valid email address")
        return value


_MAX_COMPARE_SESSIONS = 5


class CompareReportsRequest(BaseModel):
    """Schema for POST /reports/compare (Multi-Idea Comparison Matrix,
    doc 21). No session-listing endpoint exists (no accounts to scope one
    to) - the caller supplies sessionIds it already has (e.g. from its own
    locally-kept history of past validations), the same way
    GET /reports/{sessionId} already requires knowing the id upfront.
    """

    sessionIds: list[str]

    @field_validator("sessionIds")
    @classmethod
    def _validate_session_ids(cls, value: list[str]) -> list[str]:
        cleaned = [s.strip() for s in value if s and s.strip()]
        if len(cleaned) < 2:
            raise ValueError("at least 2 sessionIds are required to compare")
        if len(cleaned) > _MAX_COMPARE_SESSIONS:
            raise ValueError(f"at most {_MAX_COMPARE_SESSIONS} sessionIds can be compared at once")
        # Dedupe while preserving order - comparing an id against itself
        # twice is never a real request, just a client-side mistake.
        seen = set()
        deduped = []
        for session_id in cleaned:
            if session_id not in seen:
                seen.add(session_id)
                deduped.append(session_id)
        if len(deduped) < 2:
            raise ValueError("at least 2 distinct sessionIds are required to compare")
        return deduped


def _create_validation_session(payload: ValidateRequest, response: dict, user_id: str | None = None) -> str:
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
            "marketViability": response.get("marketViability"),
            "contradictions": response.get("contradictions"),
            "experiments": response.get("experiments"),
            "actionPlan": response.get("actionPlan"),
            # Novel features (assumption tracker + revenue model suggester) -
            # were being computed and returned in the live /validate response
            # but never stored here, so GET /reports/{id}, PDF export, email,
            # and anything else that reads a session back after the fact
            # always saw them as missing, even for a request that actually
            # produced real assumptions/revenueModels data.
            "assumptions": response.get("assumptions"),
            "revenueModels": response.get("revenueModels"),
            "verdict": response.get("verdict"),
        },
        user_id=user_id,
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
        # "sqlite" on a deployed instance means DATABASE_URL isn't set and
        # data will not survive a redeploy - see agent/db.py.
        "database": database_backend(),
    }


# --------------------------------------------------
# AUTH
# --------------------------------------------------
#
# Stateless JWT bearer tokens (agent/auth.py) - a signed-in user's own
# validations get tagged with their user id at creation time (see
# _create_validation_session's user_id param) so GET /me/history can list
# them back. Password reset is below (/auth/forgot-password and
# /auth/reset-password: a short-lived, single-use token distinct from the
# long-lived session JWT). Email verification is still not built.

@app.post("/auth/signup")
def auth_signup_route(payload: SignupRequest, request: Request):
    if _is_rate_limited(f"auth:{_client_ip(request)}", _AUTH_RATE_LIMIT):
        return _rate_limit_response("Too many attempts. Please wait a minute and try again.")
    try:
        return auth_signup(payload.email, payload.password)
    except AuthError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.post("/auth/login")
def auth_login_route(payload: LoginRequest, request: Request):
    if _is_rate_limited(f"auth:{_client_ip(request)}", _AUTH_RATE_LIMIT):
        return _rate_limit_response("Too many attempts. Please wait a minute and try again.")
    try:
        return auth_login(payload.email, payload.password)
    except AuthError as exc:
        return JSONResponse(status_code=401, content={"error": str(exc)})


@app.post("/auth/google")
def auth_google_route(payload: GoogleAuthRequest, request: Request):
    """Federated Google SSO (5-pillar spec §4.6). Same per-IP rate limit
    as the password endpoints above - an unverifiable token is still a
    failed auth attempt, not a free-standing endpoint to hammer.
    """
    if _is_rate_limited(f"auth:{_client_ip(request)}", _AUTH_RATE_LIMIT):
        return _rate_limit_response("Too many attempts. Please wait a minute and try again.")
    try:
        return auth_login_with_google(payload.idToken)
    except GoogleAuthError as exc:
        return JSONResponse(status_code=401, content={"error": str(exc)})


_FORGOT_PASSWORD_RATE_LIMIT = int(os.environ.get("FORGOT_PASSWORD_RATE_LIMIT_PER_MINUTE", "3"))
_FORGOT_PASSWORD_REPLY = {
    "status": "ok",
    "message": "If an account exists for that email, a reset link is on its way. It works once and expires in 30 minutes.",
}


def _send_reset_email_in_background(email: str, token: str) -> None:
    send_password_reset_email(email, f"{frontend_origin.rstrip('/')}/?reset={token}")


@app.post("/auth/forgot-password", status_code=202)
def auth_forgot_password_route(payload: ForgotPasswordRequest, request: Request, background: BackgroundTasks):
    """Email a single-use reset link. The answer is identical whether or not
    the address has an account, and the email is sent after the response, so
    neither the body nor the response time reveals which emails are registered.
    """
    if _is_rate_limited(f"forgot:{_client_ip(request)}", _FORGOT_PASSWORD_RATE_LIMIT):
        return _rate_limit_response("Too many reset requests. Please wait a minute and try again.")
    email = payload.email.strip()
    if is_valid_email(email):
        issued = request_password_reset(email)
        if issued is not None:
            background.add_task(_send_reset_email_in_background, issued[0], issued[1])
    return _FORGOT_PASSWORD_REPLY


@app.post("/auth/reset-password")
def auth_reset_password_route(payload: ResetPasswordRequest, request: Request):
    if _is_rate_limited(f"auth:{_client_ip(request)}", _AUTH_RATE_LIMIT):
        return _rate_limit_response("Too many attempts. Please wait a minute and try again.")
    try:
        auth_reset_password(payload.token, payload.password)
    except AuthError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return {"status": "ok"}


@app.get("/auth/me")
def auth_me(current_user: dict = Depends(require_user)):
    return {
        **current_user,
        "isAdmin": is_admin(current_user["id"]),
        **account_profile(current_user["id"]),
    }


@app.get("/me/history")
def my_history(current_user: dict = Depends(require_user)):
    return {"entries": list_sessions_for_user(current_user["id"])}


@app.post("/me/claim-session")
def claim_session_route(payload: ClaimSessionRequest, current_user: dict = Depends(require_user)):
    """Lets a validation run anonymously, then signed into right after,
    show up in this account's GET /me/history instead of staying stuck in
    the device-local list (lib/history.js) that only this browser can see.
    """
    claimed = claim_session(payload.sessionId.strip(), current_user["id"])
    if not claimed:
        return JSONResponse(
            status_code=404,
            content={"error": "That session could not be found or already belongs to another account."},
        )
    return {"claimed": True}


@app.get("/me/analytics")
def my_analytics(current_user: dict = Depends(require_user)):
    """Server-side aggregation backing the "My Ideas" dashboard - see
    agent/user_analytics.py. Signed-in only, like GET /me/history: without
    a real account there's no durable set of "my ideas" to aggregate over
    (device-local history is a frontend-only concept this endpoint has no
    way to see).
    """
    return get_user_analytics(current_user["id"])


@app.get("/metrics")
def get_metrics():
    """Raw counters - cache hit/miss and per-LLM-node success/failure
    counts (agent/metrics.py) - answering the "Open Metrics" questions
    docs/api-cost-accuracy-performance-metrics.md's §7 flagged as not yet
    measured. In-process only: resets on restart, not a persisted
    time-series, same trade-off agent/metrics.py's own docstring explains.
    """
    return metrics.snapshot()


@app.get("/admin/platform-metrics")
def get_platform_metrics_endpoint(days: int = 30, _admin: dict = Depends(require_admin)):
    """Admin-only (see agent/auth.py's require_admin) aggregation backing
    the Platform Health dashboard - see agent/platform_metrics.py for what
    each field is computed from, and what's deliberately left out (no live
    provider quota data - nothing here observes that).
    """
    days = max(1, min(days, 90))
    return get_platform_metrics(days=days)


class PipelineStateError(Exception):
    """The pipeline completed but recorded a hard failure in state['error']
    (e.g. every search source failed for every angle) - a 502 to the
    caller, distinct from an unexpected exception (500). See
    docs/architecture.md's documented /validate error contract.
    """


class NeedsDeepAnalysisRequired(Exception):
    """Raised when the pipeline short-circuited because a strategy node hit
    NeedsDeepAnalysisError (backend/agent/llm.py) - every cloud model was
    exhausted, and this request had no email on file yet to route through
    the slower local-model retry. /validate catches this specifically and
    asks the caller for an email instead of returning a 502 or silently
    serving the weaker deterministic-fallback result.
    """


def _run_pipeline_and_build_response(payload: ValidateRequest, cache_key: str, allow_local: bool = False) -> dict:
    """Runs the full LangGraph pipeline and returns the same response shape
    /validate has always returned (minus sessionId, added by the caller).
    Raises NeedsDeepAnalysisRequired or PipelineStateError for a recorded
    pipeline-state failure, or the original exception for anything
    unexpected - the caller decides how to report either, depending on
    whether it's still inside the synchronous request/response cycle or
    already running in the background for the async/email path.

    `allow_local` is True only once an email is on file (see /validate) -
    it lets every LLM-backed strategy node retry via the local Ollama model
    instead of raising NeedsDeepAnalysisError the moment cloud models are
    exhausted.
    """
    state = pipeline.invoke(
        {
            "idea": payload.idea,
            "targetCustomer": payload.targetCustomer,
            "problem": payload.problem,
            "mode": payload.mode,
            "allowLocalLlm": allow_local,
        }
    )

    if state.get("error") == NEEDS_DEEP_ANALYSIS:
        raise NeedsDeepAnalysisRequired()

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
        # Track B: cross-artifact contradiction flags
        "contradictions": state.get("contradictions"),
        # Track C: validation experiments and founder action plan
        "experiments": state.get("experiments"),
        "actionPlan": state.get("actionPlan"),
        "marketViability": state.get("marketViability"),
        # Novel features
        "assumptions": state.get("assumptions"),
        "revenueModels": state.get("revenueModels"),
        "verdict": state.get("verdict"),
        "errors": state.get("errors", {}),
        "mode": state.get("mode", "deep"),
    }

    # A degraded (deterministic-fallback) section is a model-outage result,
    # not the real answer - caching it would keep serving that weak report
    # for the whole TTL even after the models recover.
    if not _response_is_partial(response):
        _set_cached(cache_key, response)
        logger.info("Validation result cached")

    metrics.increment("cache.miss")
    events.record("cache_miss")
    events.record("idea_category", detail={"category": categorize_idea(payload.idea)})
    return response


async def _finish_async_validation(
    task: "asyncio.Task[dict]", job_id: str, payload: ValidateRequest, user_id: str | None = None, effective_email: str | None = None
) -> None:
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

    session_id = _create_validation_session(payload, response, user_id=user_id)
    complete_job(job_id, {**response, "sessionId": session_id})

    if effective_email:
        sent = send_report_email(effective_email, payload.idea, response, _report_url(session_id))
        if not sent:
            logger.warning("Report email was not delivered for job %s", job_id)


# --------------------------------------------------
# VALIDATE STARTUP IDEA
# --------------------------------------------------

@app.post("/validate")
async def validate_idea(payload: ValidateRequest, request: Request, current_user: dict | None = Depends(optional_user)):
    user_id = current_user["id"] if current_user else None
    # Use the logged-in user's account email as a fallback so reports are
    # delivered even when the user didn't toggle the email field in the form.
    effective_email = payload.email or (current_user["email"] if current_user else None)

    # ----------------------------------------------
    # Rate limit
    # ----------------------------------------------

    if _is_rate_limited(f"validate:{_client_ip(request)}", _VALIDATE_RATE_LIMIT):
        return _rate_limit_response("Too many validation requests. Please wait a minute and try again.")

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
        metrics.increment("cache.hit")
        events.record("cache_hit")

        session_id = _create_validation_session(payload, cached, user_id=user_id)

        if effective_email and _response_is_partial(cached):
            sent = send_report_email(effective_email, payload.idea, cached, _report_url(session_id))
            if not sent:
                logger.warning("Partial-result report email was not delivered for session %s", session_id)

        return {**cached, "sessionId": session_id}

    # ----------------------------------------------
    # Run LangGraph pipeline (in a worker thread - it's synchronous,
    # CPU/IO-bound crew + search work)
    # ----------------------------------------------

    # An email on file lets a strategy node fall through to the (much
    # slower) local Ollama model instead of raising NeedsDeepAnalysisRequired
    # the moment cloud models are exhausted - see _run_pipeline_and_build_response.
    #
    # Where no local tier exists at all (hosted deployments don't run
    # Ollama), asking for an email is a dead end: the email never unlocked a
    # deeper model, only a second cloud pass plus the deterministic,
    # "degraded"-flagged fallback - so anonymous founders saw a confusing
    # "enter your email" detour and then got those same results anyway. In
    # that case every request takes the allow_local path directly.
    allow_local = bool(effective_email) or not local_llm_available()
    task = asyncio.create_task(
        asyncio.to_thread(_run_pipeline_and_build_response, payload, cache_key, allow_local)
    )

    if effective_email:
        # asyncio.wait (unlike wait_for) does not cancel the task on
        # timeout, so the pipeline keeps running in the background if it's
        # not done in time - that's the whole point of this path.
        done, _pending = await asyncio.wait({task}, timeout=_ASYNC_EMAIL_THRESHOLD_SECONDS)

        if task not in done:
            job_id = create_job()
            asyncio.create_task(_finish_async_validation(task, job_id, payload, user_id=user_id, effective_email=effective_email))
            return JSONResponse(
                status_code=202,
                content={
                    "status": "processing",
                    "jobId": job_id,
                    "message": (
                        "This is taking longer than usual. We'll email your report to "
                        f"{effective_email} as soon as it's ready."
                    ),
                },
            )

    try:
        response = await task
    except NeedsDeepAnalysisRequired:
        # allow_local is False here (no email was on file - see above), so
        # this means every cloud model was exhausted and the only remaining
        # option is the slower local model. Ask for an email instead of
        # silently serving the weaker deterministic-fallback result.
        return {
            "needsEmailForDeepAnalysis": True,
            "message": (
                "This idea needs deeper reasoning to analyze accurately, which takes a few minutes "
                "on our local model instead of the usual cloud services. Enter your email and we'll "
                "send the full report as soon as it's ready."
            ),
        }
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

    session_id = _create_validation_session(payload, response, user_id=user_id)

    if effective_email and _response_is_partial(response):
        # Finished within the synchronous window, but part of it degraded
        # or failed outright - email the complete (still-shown-in-browser)
        # results anyway, same as the slow/async path, since "fast but
        # partial" is still worth the report link, not just "slow."
        sent = send_report_email(effective_email, payload.idea, response, _report_url(session_id))
        if not sent:
            logger.warning("Partial-result report email was not delivered for session %s", session_id)

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
def chat(payload: ChatRequest, request: Request):
    session_id = payload.sessionId.strip()
    message = payload.message.strip()

    if not session_id or not message:
        return JSONResponse(
            status_code=400,
            content={"error": "sessionId and message are required"},
        )

    # Per-session rate limiting already happens inside run_chat_turn via
    # session_store.reserve_chat_request. This adds a per-IP layer on top,
    # since nothing previously stopped a caller from just minting a fresh
    # session per request to dodge that per-session cap.
    if _is_rate_limited(f"chat:{_client_ip(request)}", _CHAT_RATE_LIMIT):
        return _rate_limit_response("Too many advisor messages. Please wait a minute and try again.")

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

    # Best-effort: ties the reply to the report section it's about so the
    # frontend can auto-scroll the underlying report into view. A message
    # that doesn't map to any section (small talk, etc.) just omits it.
    section = classify_section(message)
    return {"reply": reply, **({"section": section} if section else {})}


# --------------------------------------------------
# AUTOMATED PDF REPORT EXPORTER
# --------------------------------------------------

@app.post("/export-pdf")
def export_pdf_post(payload: PdfExportRequest, request: Request):
    """Compile a validation response payload (already fetched by the
    frontend) into a downloadable PDF report."""
    if _is_rate_limited(f"export-pdf:{_client_ip(request)}", _EXPORT_PDF_RATE_LIMIT):
        return _rate_limit_response("Too many PDF export requests. Please wait a minute and try again.")

    try:
        pdf_bytes = generate_dossier_pdf(payload.model_dump())
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
def export_pdf_session(session_id: str, request: Request):
    """Generate a PDF report from an existing validation session's stored
    context (see session_store.create_session)."""
    if _is_rate_limited(f"export-pdf:{_client_ip(request)}", _EXPORT_PDF_RATE_LIMIT):
        return _rate_limit_response("Too many PDF export requests. Please wait a minute and try again.")

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


# --------------------------------------------------
# CANONICAL REPORT (MILESTONE 4, TRACK D)
# --------------------------------------------------

@app.get("/reports/{session_id}")
def get_report(session_id: str, request: Request):
    """Return the canonical report object (docs/unique-features-plan.md §6)
    assembled from an existing validation session. Never reruns retrieval
    or any agent - report_assembler.py only reads out what the pipeline
    already produced for this session.
    """
    if _is_rate_limited(f"reports:{_client_ip(request)}", _EXPORT_PDF_RATE_LIMIT):
        return _rate_limit_response("Too many report requests. Please wait a minute and try again.")

    session = get_session(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found or expired."},
        )

    return assemble_report(session_id, session["context"])


@app.post("/reports/compare")
def compare_reports(payload: CompareReportsRequest, request: Request):
    """Multi-Idea Comparison Matrix (doc 21) - bundles each requested
    session's canonical report together so a caller can render them side
    by side, without a round trip per session. Never reruns retrieval or
    any agent, same as GET /reports/{sessionId} - this only reads out
    what each session's pipeline run already produced.

    No session-listing endpoint exists (no accounts to scope one to - see
    doc 19's corrected version), so the caller already has to know which
    sessionIds it wants compared; this just fetches and bundles them.

    A session_id that's expired or never existed is reported in `missing`
    rather than failing the whole request - a partial comparison (the
    sessions that ARE still valid) is still useful, the same "don't let
    one bad input erase everything else" principle the rest of this
    pipeline follows for partial failures.
    """
    if _is_rate_limited(f"reports-compare:{_client_ip(request)}", _EXPORT_PDF_RATE_LIMIT):
        return _rate_limit_response("Too many report requests. Please wait a minute and try again.")

    reports = []
    missing = []
    for session_id in payload.sessionIds:
        session = get_session(session_id)
        if not session:
            missing.append(session_id)
            continue
        reports.append(assemble_report(session_id, session["context"]))

    if len(reports) < 2:
        return JSONResponse(
            status_code=404,
            content={
                "error": "Fewer than 2 of the given sessions were found or unexpired.",
                "missing": missing,
            },
        )

    return {"reports": reports, "missing": missing}


@app.post("/reports/{session_id}/email")
def email_report(session_id: str, payload: EmailReportRequest, request: Request):
    """Email an already-generated report's HTML/text body (no PDF attachment
    - use GET /validate/{sessionId}/pdf for a direct download instead). Per
    the email rules in docs/unique-features-plan.md §7: only reads an
    existing completed report, never reruns retrieval/any agent, and never
    logs the recipient address or report contents.
    """
    if _is_rate_limited(f"report-email:{_client_ip(request)}", _REPORT_EMAIL_RATE_LIMIT):
        return _rate_limit_response("Too many email requests. Please wait a minute and try again.")

    session = get_session(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found or expired."},
        )

    report = assemble_report(session_id, session["context"])

    delivery_id = str(uuid.uuid4())
    sent = send_canonical_report_email(payload.recipient, report, _report_url(session_id))
    if not sent:
        return JSONResponse(
            status_code=502,
            content={"status": "failed", "error": "Email delivery is not available right now. Please try again shortly."},
        )

    return JSONResponse(
        status_code=202,
        content={"status": "queued", "deliveryId": delivery_id},
    )
