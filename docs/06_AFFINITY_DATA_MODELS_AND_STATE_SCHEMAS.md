# 06. Data Models, Schemas & Ephemeral Memory Architecture
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Verified & Operational  

---

## 📑 Document Table of Contents
- [1. Data Persistence Policy & Rationale](#1-data-persistence-policy--rationale)
- [2. FastAPI & Pydantic Input Data Contracts](#2-fastapi--pydantic-input-data-contracts)
- [3. Response Schema & Data Contracts](#3-response-schema--data-contracts)
- [4. Volatile In-Memory Caching System](#4-volatile-in-memory-caching-system)
- [5. Frontend Client State Persistence](#5-frontend-client-state-persistence)

---

## 1. Data Persistence Policy & Rationale

> **Correction:** this section originally described a "Zero Persistent Database
> Policy" (true of Milestones 1-2's in-memory-only design). Milestone 4 added a real
> database layer - see below.

- **Database-backed as of Milestone 4:** `backend/agent/db.py` (SQLAlchemy) persists
  validation sessions, background jobs, and the response cache to Postgres in
  production (SQLite locally/in tests) - see doc 19 for the full design. There is
  still no user-account system and no authentication: every session/job/cache row is
  bounded by a TTL and a max-row-count limit and auto-expires, but rows do live on
  disk between requests and across a restart, which "volatile RAM" and "stateless
  pipeline" both explicitly (and, as of Milestone 4, incorrectly) denied.
- **Privacy note that remains true:** submitted ideas are never used for model
  training and are never shared with a third party beyond what's needed to call the
  configured search/LLM/email providers.
- **Still stateless per LangGraph invocation:** each `pipeline.invoke()` call still
  runs through an isolated `PipelineState` dict that's discarded after the response is
  shaped - what changed is that the *shaped response* now also gets written to a
  session row, not that the pipeline itself gained cross-request state.

---

## 2. FastAPI & Pydantic Input Data Contracts

Input requests to `POST /validate` are validated using Pydantic in [`backend/main.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/main.py):

```python
class ValidateRequest(BaseModel):
    idea: str
    targetCustomer: str = ""
    problem: str = ""
    email: str = ""   # optional - triggers the async/email path if the pipeline runs long
```

### Validation Invariants
- `idea`: String, required. Whitespace trimmed and must be non-empty (`if not payload.idea.strip()`) -
  there is no minimum-length-3 rule; a single non-whitespace character passes.
- `targetCustomer`: String, optional. Default empty string.
- `problem`: String, optional. Default empty string.
- `email`: String, optional. Validated as a real email address if non-empty
  (`is_valid_email()`); invalid values are rejected with a 422 before the pipeline runs.

---

## 3. Response Schema & Data Contracts

The JSON response emitted by `POST /validate` follows a strict structure:

```typescript
interface ValidateResponse {
  summary: string;
  results: Array<{
    title: string;
    url: string;
    snippet: string;
    score: number;
    angle: string;
  }>;
  confidence: {
    marketGrowth: { agree: number; total: number };
    competitivePressure: { agree: number; total: number };
  } | null;
  marketOpportunity: {
    marketSize: string;
    trends: string[];
    segments: Array<{
      segment: string;
      painPoints: string;
      motivations: string;
      buyingBehavior: string;
    }>;
    opportunityScore: number; // 0 to 100
  } | null;
  competitors: {
    competitors: Array<{
      name: string;
      offering: string;
      positioning: string;
      estimatedPrice: "low" | "mid" | "high" | "unknown";
      featureBreadth: "narrow" | "moderate" | "broad" | "unknown";
      gap: string;
    }>;
  } | null;
  whiteSpace: {
    summary: string;
    competitionNote: string;
    opportunities: Array<{
      title: string;
      why: string;
      fit: string;
      evidence: string;
    }>;
  } | null;
  errors: {
    marketOpportunity?: string | null;
    competitors?: string | null;
  };
}
```

---

## 4. Volatile In-Memory Caching System

To minimize LLM token consumption and respect Groq free-tier rate limits, [`backend/main.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/main.py) manages a 30-minute in-memory dictionary cache:

```python
_CACHE_TTL_SECONDS = 30 * 60
_cache: dict[str, tuple[float, dict]] = {}

def _cache_key(payload: ValidateRequest) -> str:
    normalized = json.dumps(
        {
            "idea": payload.idea.strip().lower(),
            "targetCustomer": payload.targetCustomer.strip().lower(),
            "problem": payload.problem.strip().lower(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _get_cached(key: str) -> dict | None:
    now = time.time()
    if key in _cache:
        timestamp, data = _cache[key]
        if now - timestamp < _CACHE_TTL_SECONDS:
            return data
        del _cache[key]
    return None

def _set_cached(key: str, data: dict) -> None:
    _cache[key] = (time.time(), data)
```

### Invariant: Partial Failures Are Never Cached
If a response contains any active errors (`errors.marketOpportunity != null`), `_set_cached()` is bypassed, preventing transient API disruptions from persisting in cache.

---

## 5. Frontend Client State Persistence

The React application ([`frontend/src/App.jsx`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/frontend/src/App.jsx)) stores recent analysis in browser `sessionStorage` (`affinity:lastValidation`):

```javascript
const STORAGE_KEY = 'affinity:lastValidation'

function loadPersisted() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return { ...parsed, updatedAt: parsed.updatedAt ? new Date(parsed.updatedAt) : null }
  } catch {
    return null
  }
}
```

- **Tab Reload Survival:** Preserves the validation report if the user refreshes the browser or switches tabs.
- **Privacy Clean-up:** Automatically purges data when the user closes the browser tab.
