# 07. API Reference & Integration Specifications
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 3.0 · updated 2026-10-02 against `backend/main.py` on `staging`  
**Status:** Operational

> **What changed in 3.0.** Versions 1 and 2 documented only `/`, `/health`, `/validate` and
> the sign-in routes. The API has 21 routes; this version lists all of them, with their
> authentication, limits and failure responses, taken from the code. It also replaces the
> separate `api-reference.md`, which duplicated this file and had the same gaps. For the full
> `/validate` response schema see [doc 23 §9](23_AFFINITY_FIVE_PILLAR_EVIDENCE_STRATEGY_AND_GOOGLE_SSO.md#9-where-each-field-lives-in-the-response)
> and [`architecture.md` §4](architecture.md#4-api-contract).

---

## 📑 Document Table of Contents
- [1. Overview & Service URLs](#1-overview--service-urls)
- [2. Authentication, CORS & Rate Limits](#2-authentication-cors--rate-limits)
- [3. Route Summary](#3-route-summary)
- [4. Validation Routes](#4-validation-routes)
- [5. Report, Advisor & Delivery Routes](#5-report-advisor--delivery-routes)
- [6. Account & Admin Routes](#6-account--admin-routes)
- [7. Partial Failure Contract](#7-partial-failure-contract)
- [8. Integration Snippets](#8-integration-snippets)

---

## 1. Overview & Service URLs

- **Local:** `http://localhost:8000`
- **Hosted:** the Render web service named in [`../DEPLOYMENT.md`](../DEPLOYMENT.md)
- **Interactive docs:** FastAPI serves Swagger UI at `/docs` on any running instance.

---

## 2. Authentication, CORS & Rate Limits

- **Anonymous use works.** `/validate`, `/chat`, `/reports/*` and the PDF routes need no
  token. A report is addressed by its random `sessionId`, which acts as a share link: anyone
  who holds it can read that report, its PDF and its chat.
- **Optional token on `/validate`.** A bearer token saves the run to the account. A header
  that is present but invalid or expired is rejected with `401`, not silently treated as
  anonymous.
- **Account routes** (`/auth/me`, `/me/*`) require a valid bearer token. **Admin route**
  (`/admin/platform-metrics`) additionally requires an account listed in `ADMIN_EMAILS`
  (`403` otherwise).
- **Tokens:** HS256 JWT, 30 days. Sign-in routes are `POST /auth/signup`, `/auth/login` and
  `/auth/google` (a Google ID token in; the same `{ token, user }` out).
- **CORS:** allowed origins come from `FRONTEND_ORIGIN` (default `http://localhost:5173`).
- **Rate limits** are per client IP per minute and return `429`. Defaults, each overridable
  by an environment variable:

| Group | Default per minute | Variable |
|---|---|---|
| `/validate` | 10 | `VALIDATE_RATE_LIMIT_PER_MINUTE` |
| `/chat` | 30 | `CHAT_RATE_LIMIT_PER_MINUTE` |
| PDF export and `/reports/*` reads | 10 | `EXPORT_PDF_RATE_LIMIT_PER_MINUTE` |
| `/reports/{id}/email` | 5 | `REPORT_EMAIL_RATE_LIMIT_PER_MINUTE` |
| Sign-in routes and `/auth/reset-password` | 8 | `AUTH_RATE_LIMIT_PER_MINUTE` |
| `/auth/forgot-password` | 3 | `FORGOT_PASSWORD_RATE_LIMIT_PER_MINUTE` |

---

## 3. Route Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | none | Service catalog |
| GET | `/health` | none | Liveness probe (also reports the database kind) |
| POST | `/validate` | optional | Run the validation pipeline |
| GET | `/validate/status/{job_id}` | none | Poll a background validation |
| POST | `/chat` | none | One advisor turn for a report |
| GET | `/validate/{session_id}/pdf` | none | Download a report as PDF |
| POST | `/export-pdf` | none | Build a PDF from a response body you supply |
| GET | `/reports/{session_id}` | none | Fetch the canonical saved report |
| POST | `/reports/compare` | none | Fetch 2 to 5 reports for side-by-side comparison |
| POST | `/reports/{session_id}/email` | none | Email a saved report to an address |
| POST | `/auth/signup` | none | Create an account |
| POST | `/auth/login` | none | Sign in |
| POST | `/auth/google` | none | Sign in with Google |
| POST | `/auth/forgot-password` | none | Email a single-use password-reset link |
| POST | `/auth/reset-password` | none | Set a new password from a reset token |
| GET | `/auth/me` | token | Current user (includes `isAdmin`) |
| GET | `/me/history` | token | The account's saved validations |
| POST | `/me/claim-session` | token | Attach an anonymous session to the account |
| GET | `/me/analytics` | token | Aggregates behind the founder dashboard |
| GET | `/metrics` | none | In-process counters (cache, per-node success and failure) |
| GET | `/admin/platform-metrics` | admin | Platform health aggregates, `days` 1 to 90 |

---

## 4. Validation Routes

### 4.1 `POST /validate`

**Request body**

```json
{
  "idea": "AI-powered invoice management for freelance photographers",
  "targetCustomer": "Freelance wedding photographers",
  "problem": "Manual payment reminders take hours and clients miss due dates",
  "email": "",
  "mode": "deep"
}
```

| Field | Rules |
|---|---|
| `idea` | required, up to 2,500 characters |
| `targetCustomer` | optional, up to 600 characters |
| `problem` | optional, up to 1,500 characters |
| `email` | optional; a signed-in user's account email is used if omitted |
| `mode` | `"deep"` (default, full pipeline) or `"quick"` (core market validation; skips SWOT, viability, MVP, GTM, contradictions, experiments, action plan, revenue models) |

**Four possible outcomes**

| Status | Body | When |
|---|---|---|
| `200` | The report plus `sessionId` | Finished normally |
| `200` | `{ "needsEmailForDeepAnalysis": true, "message": "…" }` | Every cloud model was exhausted, a slower local model exists, and no email is on file. Resend with `email` set |
| `202` | `{ "status": "processing", "jobId": "…", "message": "…" }` | An email is on file and the run took longer than the threshold (60 s by default). It continues in the background and the report is emailed; poll `/validate/status/{jobId}` |
| `502` / `500` | `{ "error": "…" }` | The pipeline recorded a hard failure (for example every search source failed), or an unexpected exception |

Identical requests are served from a 30-minute cache. Only responses with no section errors
are cached.

**Success response (abridged)**

```json
{
  "summary": "Found 12 relevant sources for \"AI-powered invoice management\"…",
  "results": [
    { "title": "Invoicing Software Market Size 2026", "url": "https://example.com/report",
      "snippet": "…", "score": 0.89, "angle": "Market size & trends" }
  ],
  "confidence": {
    "agreeingSources": 6, "totalSources": 8, "percentage": 75, "label": "6/8 sources agree",
    "sourceCoverage": { "claimsWithSource": 18, "totalClaims": 24, "percentage": 75 },
    "averageRelevance": 0.71,
    "crossSourceAgreement": { "claimsWithMultipleSources": 7, "totalClaims": 24, "percentage": 29 },
    "directEvidenceRatio": { "direct": 18, "inferred": 6, "percentage": 75 },
    "sourceRecency": { "sourcesWithKnownDate": 5, "totalSources": 12, "medianAgeDays": 94.5 }
  },
  "marketOpportunity": {
    "marketSize": "…",
    "tam": { "text": "$2.4B global invoicing software market (2026)", "sourceIds": ["src-1"] },
    "sam": { "text": "About $480M (estimate)", "sourceIds": [], "estimated": true,
             "assumptions": "Assumes 20% of the TAM is reachable by small studios." },
    "som": null,
    "trends": [ { "text": "…", "sourceIds": ["src-1"] } ],
    "segments": [ { "segment": "…", "painPoints": "…", "motivations": "…", "buyingBehavior": "…", "sourceIds": ["src-1"] } ],
    "opportunityScore": 78
  },
  "competitors": { "competitors": [ { "name": "FreshBooks", "classification": "direct", "offering": "…", "gap": "…" } ] },
  "whiteSpace": { "summary": "…", "opportunities": [ { "title": "…", "why": "…", "fit": "…", "evidence": "…" } ] },
  "errors": {},
  "sessionId": "…"
}
```

The full response also carries `swot`, `mvp`, `gtm`, `viabilityIndex`, `contradictions`,
`experiments`, `actionPlan`, `assumptions`, `revenueModels` and `verdict`. A tier carrying
`"estimated": true` is the model's own working from the TAM, never a sourced figure; it has
no `sourceIds` and always has `assumptions`.

### 4.2 `GET /validate/status/{job_id}`

| Status | Body |
|---|---|
| `200` | `{ "status": "processing" }` while running |
| `200` | `{ "status": "complete", …the full report }` when finished |
| `502` | `{ "status": "failed", "error": "…" }` |
| `404` | `{ "error": "Job not found or expired." }` (jobs are kept for 2 hours) |

---

## 5. Report, Advisor & Delivery Routes

### 5.1 `POST /chat`

Body: `{ "sessionId": "…", "message": "…" }` (message up to 1,200 characters). Returns
`{ "reply": "…", "section": { "tab", "id", "label" } }`. `section` is present when the
question maps to a report section, so the client can open that tab and scroll to it. Errors:
`400` missing fields, `404` unknown or expired session, `429` rate limit, `502` the advisor
could not answer.

### 5.2 `GET /validate/{session_id}/pdf` and `POST /export-pdf`

Return `application/pdf` (an attachment). The `GET` form builds the PDF from a saved session
(`404` if unknown or expired). The `POST` form accepts a full response body and builds the PDF
from it. Both use ReportLab and return `500` with an error message if the export fails.

### 5.3 `GET /reports/{session_id}`

Returns the canonical saved report. `404` if the session is unknown or expired (sessions are
kept for 7 days).

### 5.4 `POST /reports/compare`

Body: `{ "sessionIds": ["…", "…"] }`, 2 to 5 distinct ids. Returns
`{ "reports": [...], "missing": [...] }`. `404` if fewer than two sessions were found.

### 5.5 `POST /reports/{session_id}/email`

Body: `{ "recipient": "name@example.com" }`. Returns `202` with `{ "status": "queued",
"deliveryId": "…" }` on success, `404` for an unknown session and `502` when email delivery
is not available. The email carries a summary and a link to the report; it does not attach a
PDF.

---

## 6. Account & Admin Routes

- `POST /auth/signup` and `/auth/login`: body `{ "email", "password" }`; return `{ token, user }`.
- `POST /auth/google`: body `{ "idToken" }`; the signature and audience are re-verified on the server.
- `POST /auth/forgot-password`: body `{ "email" }`. Always answers `202` with the same message
  (`{ "status": "ok", "message": "If an account exists for that email, a reset link is on its way…" }`),
  whether or not the address has an account or is even well-formed, and sends the email after
  responding, so neither the body nor the timing reveals which emails are registered. The link
  is `<FRONTEND_ORIGIN>/?reset=<token>`. The token is random, single-use and valid for 30 minutes;
  only its SHA-256 hash is stored, and a new request replaces the earlier link. `429` when rate limited.
- `POST /auth/reset-password`: body `{ "token", "password" }` (password at least 8 characters).
  `200 { "status": "ok" }` and the token is consumed in the same transaction that changes the
  password; `400 { "error": "…" }` for an invalid, expired or already-used token or a too-short
  password. It does not sign the user in, and tokens (JWTs) already issued stay valid until they expire.
- `GET /auth/me`: `{ id, email, isAdmin, … }`. A `401` here is how the client learns its stored token is no longer valid.
- `GET /me/history`: `{ "entries": [...] }`, the account's saved validations.
- `POST /me/claim-session`: body `{ "sessionId" }`; attaches a run made anonymously to the account. `{ "claimed": true }`, or `404` if the session is missing or already owned by another account.
- `GET /me/analytics`: the aggregates behind the founder dashboard.
- `GET /metrics`: in-process counters (cache hit and miss, per-node success and failure). They reset on restart.
- `GET /admin/platform-metrics?days=30`: validations per day, cache hit rate, API success rate, deep-analysis rate, latency by node, model usage, recent errors and email delivery, backed by the durable `events` log.

---

## 7. Partial Failure Contract

A failed section does not fail the request. The API still returns `200` with that section
`null` (or carrying a `degraded` flag where a rule-based fallback was used) and a message
under `errors`:

```json
{
  "summary": "Found 9 relevant sources for \"Smart Water Bottle\"…",
  "results": [ "…" ],
  "marketOpportunity": null,
  "competitors": { "competitors": [ { "name": "HidrateSpark", "offering": "Smart hydration tracker" } ] },
  "whiteSpace": null,
  "errors": {
    "marketOpportunity": "This analysis hit a temporary usage limit. Please try again in a moment."
  }
}
```

A section built by a deterministic fallback (for example revenue models inferred from
competitor pricing) carries `"degraded": true` and the UI labels it.

---

## 8. Integration Snippets

### cURL
```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"idea": "AI meal prep planner for busy parents", "targetCustomer": "Working parents", "problem": "No time to plan meals"}'
```

### Python (`requests`)
```python
import requests

res = requests.post(
    "http://localhost:8000/validate",
    json={"idea": "AI meal prep planner for busy parents", "targetCustomer": "Working parents"},
)
data = res.json()
if data.get("needsEmailForDeepAnalysis"):
    print(data["message"])          # resend with "email" set
elif res.status_code == 202:
    print("Running in the background:", data["jobId"])
else:
    print("Score:", (data.get("marketOpportunity") or {}).get("opportunityScore"))
```

### JavaScript (`fetch`)
```javascript
const res = await fetch('http://localhost:8000/validate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ idea: 'AI meal prep planner for busy parents' }),
});
const data = await res.json();
```


## 9. Fields added 2026-10-03

All are additive and optional; clients that ignore them keep working. Reports saved before
these fields existed do not carry them.

| Field | Where | Shape |
|---|---|---|
| `verification` | inside `marketOpportunity`, `swot`, `mvp`, `gtm` | `{ "ran": bool, "checked": int, "removed": [{ "text": str, "sourceIds": [str] }] }`. `ran: false` means the source check did not run for that section |
| `kpis` | inside `gtm` | `[{ "name": str, "target": str, "timeframe": str }]`, up to 5. Absent when the go-to-market step used its rule-based fallback |
| `sprint` | inside `actionPlan` | `{ "weeks": [{ "week": 1-4, "title": str, "tasks": [{ "task": str, "confirmsIf": str, "killsIf": str }] }], "note": str }` |
| `interviewScript` | inside `actionPlan` | `{ "audience": str, "rules": [str], "opening": [str], "probes": [{ "assumption", "ask", "listenFor", "redFlag" }], "closing": [str] }` |
| `pipelineTrace` | top level of the `/validate` response and the saved report | `[{ "node": str, "seconds": float, "models": [str] }]` in the order steps finished. `models` is empty for steps that make no model call |
