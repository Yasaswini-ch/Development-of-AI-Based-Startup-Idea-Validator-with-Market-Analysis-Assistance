# Security, Privacy, and AI Ethics Specification
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 3.0 · updated 2026-09-26 against `staging`  
**Status:** Verified & Operational  

---

## 1. Overview & Core Security Commitments

Affinity validates early-stage startup ideas using automated web retrieval and LLM reasoning. Founders submitting unreleased or proprietary business concepts require strict data privacy, minimal retention, and transparent AI reasoning.

### Core Architecture Commitments
1. **Bounded Retention (not zero storage):** Since Milestone 4, submitted ideas and generated reports are stored in a database (Postgres in production, SQLite locally) so they survive restarts and can be revisited. Every validation session auto-expires 7 days after its last update (200-row cap). *Earlier versions of this document said "zero persistent storage"; that stopped being true when `backend/agent/db.py` shipped.* See §2.3 for the full retention table.
2. **Short-Lived Response Cache:** The `/validate` response cache is a database table with a 30-minute TTL (`_CACHE_TTL_SECONDS = 1800`), keyed by a SHA-256 hash of the normalized input.
3. **No Third-Party Model Training:** API integrations with LLM providers (Groq) and search providers (Tavily) operate under commercial terms prohibiting the use of submitted prompt payloads for model retraining.
4. **Deterministic Evidence Grounding:** Strategic insights are generated only from retrieved web evidence to prevent AI hallucinations.

---

## 2. Information Security & Data Life-Cycle

### 2.1 Data Flow Architecture

```mermaid
sequenceDiagram
    participant Founder as Founder (Browser)
    participant API as FastAPI Backend
    participant Search as Tavily / DDG Search API
    participant LLM as Groq LLM API

    Founder->>API: POST /validate (Idea, Customer, Problem)
    Note over API: Normalizes query payload & computes SHA-256 hash
    API->>Search: Queries (Anonymized market research angles)
    Search-->>API: Scraped web snippets
    API->>LLM: Formatted Prompt + Web Snippets (market_opportunity)
    LLM-->>API: Structured JSON summary
    Note over API: Executes local spaCy NER & Regex calculations (zero network calls)
    API-->>Founder: JSON Validation Response
    Note over API: Session stored (7-day TTL); cached response purged after 30 minutes
```

---

### 2.2 Response Cache Implementation

> This section originally described an in-memory dict. The cache now lives in the
> `validation_cache` database table; the key derivation and TTL below are unchanged.

The caching engine in [`backend/main.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/main.py) uses cryptographic SHA-256 hashing to generate cache keys from normalized input parameters:

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
```

- **Partial Failure Protection:** Responses containing errors (`errors.marketOpportunity != null`) are **never cached**, ensuring transient upstream disruptions do not persist.
- **Client Storage:** The in-progress result is kept in `sessionStorage`, so it survives a tab reload and is cleared when the tab closes. The auth token, device-local history and compare basket are kept in `localStorage`, which persists until sign-out or cleared site data. On sign-in, sign-out and account switch the app clears the stored validation state and the device-local history and compare lists, and it only writes to those device lists while signed out (a signed-in account's history lives server-side), so one person's ideas don't show up for the next person on a shared computer.

### 2.3 Accounts, Access Control & Retention

Full detail in [doc 19](19_AFFINITY_MILESTONE_3_POSTGRESQL_AUTH_AND_DATA_PERSISTENCE.md).

- **Optional accounts.** Email + password (minimum 8 characters), bcrypt-hashed. Anonymous
  validation still works. Login returns the same error for unknown email and wrong
  password, so accounts can't be enumerated. Auth endpoints are rate-limited per IP.
- **Tokens.** HS256 JWT signed with `AUTH_SECRET_KEY`, valid 30 days, stored in the
  browser's `localStorage` (readable by scripts on the page, the usual trade-off against
  an httpOnly cookie). No server-side revocation.
- **Admin role.** A single `is_admin` flag, granted only via the `ADMIN_EMAILS`
  environment variable or direct SQL, checked fresh on every request. It unlocks the
  read-only Platform Health metrics and nothing else.
- **Session links.** Report, chat, PDF and compare endpoints accept a session id without
  an ownership check. The id is a random UUID and acts as a share link.
- **Operational log.** The `events` table stores node timings, model names, cache
  hits/misses, error types, idea **categories** and email outcomes. It never stores idea
  text or email addresses.

| Data | Where | Retention |
|---|---|---|
| Validation session (idea, results, chat) | `sessions` | 7 days after last update; 200 rows max |
| Async job result | `jobs` | 2 hours; 200 rows max |
| Response cache | `validation_cache` | 30 minutes |
| Operational events | `events` | 90 days; 200,000 rows max |
| Account (email, password hash, admin flag) | `users` | Until deleted by an operator |

> Render's free Postgres is deleted 30 days after creation, which removes all of the
> above at once. See [Known Limitations](known-limitations-and-future-work.md).

---

## 3. Privacy & Search Anonymization

When an idea is submitted, Affinity's retrieval layer in [`backend/agent/retrieval.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/retrieval.py) generates up to 5 generalized search queries:
1. `Market size & trends`
2. `Competitors`
3. `Industry news`
4. `Customer demand`
5. `How others solve this`

### Anonymization Practices
- Search queries contain only generalized market descriptors derived from the user's idea.
- User IP addresses, browser fingerprinting, and personally identifiable information (PII) are stripped before sending requests to Tavily or DuckDuckGo.
- Domain filtering (`_EXCLUDED_DOMAINS`) strips academic paper hubs (`arxiv.org`, `ncbi.nlm.nih.gov`) and generic affiliate directory sites (`alternativeto.net`, `saashub.com`) to prevent privacy leaks and maintain signal quality.

---

## 4. AI Ethics & Hallucination Mitigation

### 4.1 Factual Metric Grounding
A primary threat in AI-based financial validation is "hallucinated market figures" (e.g., invented TAM/SAM statistics or fabricated CAGR percentages).

Affinity enforces strict negative constraints in [`backend/agent/market_agent.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/market_agent.py):
- The model is instructed to cite TAM, SAM, or CAGR metrics **only** when retrieved web snippets explicitly contain those figures.
- If market metrics are missing in search results, the system explicitly reports: *"TAM/SAM figures are not clear from the provided sources."*

### 4.2 Transparent Partial Failure UI
If an LLM call fails, the application does not substitute fake placeholder content. Instead:
- The section returns `null` with an error description in `errors.marketOpportunity`.
- The frontend renders an inline `UnavailableCard` informing the user of the temporary disruption while preserving valid competitor and web source results.

---

## 5. Decision Support Disclaimer

Affinity is an **automated market research assistant** designed for preliminary feasibility screening.

- Outputs do not constitute formal financial, legal, or investment advice.
- Opportunity Scores (0–100) are comparative heuristic indicators calculated from available online search density and growth indicators.
- Founders should perform direct customer interviews and legal due diligence before committing capital.
