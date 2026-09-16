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

Affinity operates under a **Zero Persistent Database Policy**:
- **No SQL / NoSQL Storage:** Submitted startup ideas, target demographics, and generated reports are stored strictly in volatile RAM.
- **Privacy Assurance:** Unreleased startup concepts are never logged to a disk-backed database or shared with external model trainers.
- **Stateless Pipeline:** Every validation request executes through an isolated LangGraph state dictionary (`PipelineState`) that is garbage-collected upon completion.

---

## 2. FastAPI & Pydantic Input Data Contracts

Input requests to `POST /validate` are validated using Pydantic in [`backend/main.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/main.py):

```python
class ValidateRequest(BaseModel):
    idea: str
    targetCustomer: str = ""
    problem: str = ""
```

### Validation Invariants
- `idea`: String, required. Whitespace trimmed. Must contain at least 3 non-whitespace characters.
- `targetCustomer`: String, optional. Default empty string.
- `problem`: String, optional. Default empty string.

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
