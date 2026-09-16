# 07. API Reference & Integration Specifications
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Operational  

---

## 📑 Document Table of Contents
- [1. Overview & Service URLs](#1-overview--service-urls)
- [2. CORS & Security Policy](#2-cors--security-policy)
- [3. Endpoints Specification](#3-endpoints-specification)
- [4. Partial Failure Contract](#4-partial-failure-contract)
- [5. Integration Snippets (cURL, Python, JS, Go)](#5-integration-snippets-curl-python-js-go)

---

## 1. Overview & Service URLs

The Affinity API provides REST endpoints for automated startup validation.

- **Local Endpoint:** `http://localhost:8000`
- **Staging / Production:** `https://startup-validator-backend.onrender.com`

---

## 2. CORS & Security Policy

- **Authentication:** Public endpoints (`/validate` does not require an API key).
- **CORS Allowed Origins:** Managed via `FRONTEND_ORIGIN` env variable (defaults to `http://localhost:5173`).
- **Methods Allowed:** `GET`, `POST`, `OPTIONS`.

---

## 3. Endpoints Specification

### 3.1 `GET /` — Service Catalog
Returns service metadata.

```json
{
  "message": "Affinity API is running",
  "status": "ok",
  "docs": "/docs",
  "health": "/health",
  "validate_endpoint": "/validate"
}
```

---

### 3.2 `GET /health` — Liveness Check
Health probe endpoint.

```json
{
  "status": "ok",
  "service": "Affinity API"
}
```

---

### 3.3 `POST /validate` — Validation Pipeline Execution

#### Request Headers
`Content-Type: application/json`

#### Request Body
```json
{
  "idea": "AI-powered invoice management for freelance photographers",
  "targetCustomer": "Freelance wedding photographers",
  "problem": "Manual payment reminders take hours and clients miss due dates"
}
```

#### Success Response `200 OK`
```json
{
  "summary": "Found 12 relevant sources for \"AI-powered invoice management\", covering Market size & trends, Competitors, Industry news.",
  "results": [
    {
      "title": "Invoicing Software Market Size 2026",
      "url": "https://example.com/report",
      "snippet": "The global invoicing market is valued at $2.4B growing at 11% CAGR.",
      "score": 0.89,
      "angle": "Market size & trends"
    }
  ],
  "confidence": {
    "marketGrowth": { "agree": 4, "total": 5 },
    "competitivePressure": { "agree": 2, "total": 4 }
  },
  "marketOpportunity": {
    "marketSize": "The invoicing software market is valued at $2.4B globally with an 11% CAGR.",
    "trends": [
      "Automated SMS payment reminders",
      "Instant deposit releases upon gallery approval"
    ],
    "segments": [
      {
        "segment": "Wedding Photographers",
        "painPoints": "Clients delay final balance payments",
        "motivations": "Automate contract signing and deposit collection",
        "buyingBehavior": "Prefer monthly subscriptions priced under $25/month"
      }
    ],
    "opportunityScore": 78
  },
  "competitors": {
    "competitors": [
      {
        "name": "FreshBooks",
        "offering": "General accounting suite for small business",
        "positioning": "Established general financial software",
        "estimatedPrice": "mid",
        "featureBreadth": "broad",
        "gap": "Lacks photo-gallery delivery triggers"
      }
    ]
  },
  "whiteSpace": {
    "summary": "Strong market growth with moderate competitor concentration.",
    "competitionNote": "Existing tools target general accounting rather than photo-specific deposit triggers.",
    "opportunities": [
      {
        "title": "Gallery Delivery Payment Lock",
        "why": "Photographers require full balance settlement before delivering high-res photos.",
        "fit": "High fit for photographer pain points.",
        "evidence": "3 search sources mention deposit dispute friction."
      }
    ]
  },
  "errors": {}
}
```

---

## 4. Partial Failure Contract

If an upstream LLM call rate-limits or fails, the API returns **`200 OK`** with partial data and populates `errors.marketOpportunity`:

```json
{
  "summary": "Found 9 relevant sources for \"Smart Water Bottle\"...",
  "results": [ ... ],
  "confidence": { "marketGrowth": { "agree": 3, "total": 4 }, "competitivePressure": { "agree": 0, "total": 3 } },
  "marketOpportunity": null,
  "competitors": { "competitors": [ { "name": "HidrateSpark", "offering": "Smart hydration tracker" } ] },
  "whiteSpace": null,
  "errors": {
    "marketOpportunity": "This analysis hit a temporary usage limit. Please try again in a moment.",
    "competitors": null
  }
}
```

---

## 5. Integration Snippets

### cURL
```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"idea": "AI meal prep planner for busy parents"}'
```

### Python (`requests`)
```python
import requests

url = "http://localhost:8000/validate"
payload = {"idea": "AI meal prep planner for busy parents"}

res = requests.post(url, json=payload)
data = res.json()
print("Score:", data.get("marketOpportunity", {}).get("opportunityScore"))
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
