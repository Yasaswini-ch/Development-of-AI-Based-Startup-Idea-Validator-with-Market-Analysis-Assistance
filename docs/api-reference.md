# API Reference & Developer Integration Guide
**Project:** Affinity — AI-Based Startup Idea Validator  
**Document Version:** September 2026 · Milestones 1 & 2  

---

## 1. Overview & Base URLs

The Affinity Backend is built using FastAPI and exposes endpoints for validating startup ideas, checking service health, and inspecting system metrics.

### Base URLs
- **Local Development:** `http://localhost:8000`
- **Staging / Production (Render):** `https://startup-validator-backend.onrender.com`

---

## 2. Authentication & CORS Policy

- **Authentication:** All current endpoints are public and do not require API keys.
- **CORS:** Controlled via the `FRONTEND_ORIGIN` environment variable (defaults to `http://localhost:5173`). Allowed HTTP methods: `GET`, `POST`.

---

## 3. Endpoints

### 3.1 `GET /` — API Information
Returns API metadata and documentation links.

#### Response `200 OK`
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

### 3.2 `GET /health` — Health Check
Liveness probe for deployment platforms (Render, Kubernetes).

#### Response `200 OK`
```json
{
  "status": "ok",
  "service": "Affinity API"
}
```

---

### 3.3 `POST /validate` — Validate Startup Idea
Executes the multi-agent validation pipeline over a submitted startup concept.

#### Request Headers
`Content-Type: application/json`

#### Request Body Schema
```typescript
interface ValidateRequest {
  idea: string;           // Required: Core concept (e.g. "AI invoice app for freelancers")
  targetCustomer?: string; // Optional: Primary user segment (e.g. "Solo photographers")
  problem?: string;        // Optional: Problem statement (e.g. "Chasing unpaid invoices")
}
```

#### Example Request Body
```json
{
  "idea": "AI-powered invoice management for freelance photographers",
  "targetCustomer": "Freelance wedding and commercial photographers",
  "problem": "Manual payment reminders take hours and clients miss due dates"
}
```

---

#### Success Response Schema `200 OK`

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
    opportunityScore: number; // 0 - 100
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

#### Example Complete Response `200 OK`

```json
{
  "summary": "Found 12 relevant sources for \"AI-powered invoice management\", covering Market size & trends, Competitors, Industry news.",
  "results": [
    {
      "title": "Freelance Invoicing Software Market Analysis 2026",
      "url": "https://example.com/report",
      "snippet": "The global invoicing software market is valued at $2.4B growing at 11% CAGR.",
      "score": 0.88,
      "angle": "Market size & trends"
    }
  ],
  "confidence": {
    "marketGrowth": { "agree": 4, "total": 5 },
    "competitivePressure": { "agree": 2, "total": 4 }
  },
  "marketOpportunity": {
    "marketSize": "The invoicing software market is growing at 11% CAGR globally.",
    "trends": [
      "Automated SMS payment reminders",
      "Integrated instant-payout options"
    ],
    "segments": [
      {
        "segment": "Freelance Photographers",
        "painPoints": "Unpredictable cash flow and overdue invoices",
        "motivations": "Faster payment processing and minimal admin time",
        "buyingBehavior": "Prefer monthly software subscriptions under $25/mo"
      }
    ],
    "opportunityScore": 78
  },
  "competitors": {
    "competitors": [
      {
        "name": "FreshBooks",
        "offering": "Full accounting suite for small businesses",
        "positioning": "Established all-in-one financial tool",
        "estimatedPrice": "mid",
        "featureBreadth": "broad",
        "gap": "Complex UI for solo creative freelancers"
      }
    ]
  },
  "whiteSpace": {
    "summary": "High market growth with moderate competitor saturation.",
    "competitionNote": "Incumbents focus on general accounting rather than photo-specific deposit milestones.",
    "opportunities": [
      {
        "title": "Automated Milestone Contracts",
        "why": "Photographers require deposit-linked releases before delivering high-res files.",
        "fit": "High alignment with freelance workflow pain points.",
        "evidence": "3 search sources mention deposit dispute friction."
      }
    ]
  },
  "errors": {}
}
```

---

### 3.4 Partial Failure Isolation Contract

If an upstream LLM call rate-limits or fails, the endpoint still returns **`200 OK`**. Upstream failures are isolated to individual response keys:

```json
{
  "summary": "Found 8 relevant sources for \"Smart Water Bottle\"...",
  "results": [ ... ],
  "confidence": { "marketGrowth": { "agree": 3, "total": 4 }, "competitivePressure": { "agree": 0, "total": 3 } },
  "marketOpportunity": null,
  "competitors": {
    "competitors": [
      { "name": "HidrateSpark", "offering": "Smart water bottle with LED reminders" }
    ]
  },
  "whiteSpace": null,
  "errors": {
    "marketOpportunity": "This analysis hit a temporary usage limit. Please try again in a moment.",
    "competitors": null
  }
}
```

---

## 4. Integration Code Examples

### cURL
```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "idea": "AI meal prep planner for busy parents",
    "targetCustomer": "Parents working full-time",
    "problem": "Lack of time to organize weekly family meals"
  }'
```

### Python (`requests`)
```python
import requests

url = "http://localhost:8000/validate"
payload = {
    "idea": "AI meal prep planner for busy parents",
    "targetCustomer": "Parents working full-time",
    "problem": "Lack of time to organize weekly family meals"
}

response = requests.post(url, json=payload)
data = response.json()

print(f"Summary: {data['summary']}")
if data['marketOpportunity']:
    print(f"Opportunity Score: {data['marketOpportunity']['opportunityScore']}")
```

### JavaScript (`fetch`)
```javascript
async function validateIdea(ideaPayload) {
  const res = await fetch('http://localhost:8000/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ideaPayload),
  });
  
  const data = await res.json();
  if (data.errors?.marketOpportunity) {
    console.warn('Market section failed:', data.errors.marketOpportunity);
  }
  return data;
}
```
