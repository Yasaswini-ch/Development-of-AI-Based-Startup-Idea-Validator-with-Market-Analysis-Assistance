# 03. Software Requirements Specification (SRS)
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Verified & Operational  

---

## 📑 Document Table of Contents
- [1. Introduction & System Scope](#1-introduction--system-scope)
- [2. User Personas & User Stories](#2-user-personas--user-stories)
- [3. Functional Requirements (FRs)](#3-functional-requirements-frs)
- [4. Non-Functional Requirements (NFRs)](#4-non-functional-requirements-nfrs)
- [5. Input & Output Boundary Contracts](#5-input--output-boundary-contracts)
- [6. System Constraints & Assumptions](#6-system-constraints--assumptions)

---

## 1. Introduction & System Scope

This document specifies the formal Functional and Non-Functional Software Requirements for **Affinity**. Affinity is an automated, web-grounded validation engine that takes user-submitted startup ideas, queries search provider APIs across 5 research angles, processes text using a hybrid LLM/NER pipeline, and renders a structured market analysis.

---

## 2. User Personas & User Stories

### User Story 1: Idea Feasibility Screening
* **As a** Solo Bootstrapper,  
* **I want to** submit a 2-sentence startup idea and receive an immediate feasibility score and competitor overview,  
* **So that** I don't waste months coding a project with zero market demand.

### User Story 2: Investor Pitch Grounding
* **As a** Student Entrepreneur,  
* **I want to** view cited web sources, verified market growth rates, and customer segment profiles,  
* **So that** I can back up my business plan in front of pitch competition judges.

### User Story 3: Feature Gap Analysis
* **As a** Product Manager,  
* **I want to** inspect a 3x3 Competitor Positioning Grid and White-Space Feature Gaps,  
* **So that** I can justify new product expansion roadmaps with objective market evidence.

---

## 3. Functional Requirements (FRs)

| ID | Requirement Title | Description | Priority |
|---|---|---|---|
| **FR-01** | Multi-Angle Query Expansion | System shall expand a submitted startup concept into up to 5 research queries (`Market size & trends`, `Competitors`, `Industry news`, `Customer demand`, `How others solve this`). | High |
| **FR-02** | Live Search Retrieval | System shall execute search queries against Tavily API or fall back to DuckDuckGo/Wikipedia/Hacker News if Tavily is unavailable. | High |
| **FR-03** | Academic Noise Filtering | System shall automatically strip out research repository domains (`arxiv.org`, `ncbi.nlm.nih.gov`) and directory aggregator sites (`saashub.com`). | Medium |
| **FR-04** | Market Opportunity Analysis | System shall execute an LLM agent to summarize market size, growth, TAM/SAM/CAGR figures (if present in sources), 4 market trends, and 4 customer segment profiles. | High |
| **FR-05** | Local Competitor Extraction | System shall process search snippets using local spaCy `en_core_web_sm` NER to identify competitors without making LLM calls. | High |
| **FR-06** | 3x3 Positioning Grid | System shall pattern-match pricing and feature breadth to classify competitors into a 3x3 grid (`low/mid/high` price $\times$ `narrow/moderate/broad` breadth). | Medium |
| **FR-07** | Source Agreement Calculation | System shall calculate regex-based consensus metrics (e.g., *"4/5 sources agree market is growing"*). | Medium |
| **FR-08** | White-Space Gap Synthesis | System shall algorithmically synthesize unaddressed market opportunities from pain points and competitor density. | Medium |
| **FR-09** | Opportunity Score Formulation | System shall calculate a deterministic 0–100 integer score reflecting market viability. | High |
| **FR-10** | Partial Failure UI Rendering | System shall return partial JSON responses with inline `errors` flags if an upstream node fails, rendering `UnavailableCard` in UI. | High |

---

## 4. Non-Functional Requirements (NFRs)

### 4.1 Performance & Latency (NFR-01 to NFR-03)
- **NFR-01 (Response Time):** End-to-end processing time for a complete validation request shall not exceed **15 seconds** under normal load.
- **NFR-02 (API Frugality):** The backend pipeline shall execute **at most 1 LLM call** per user validation request.
- **NFR-03 (Token Optimization):** The primary Groq LLM model (`qwen3.8-27b`) shall use `reasoning_effort="none"` to keep output token consumption under free-tier per-minute caps.

### 4.2 Privacy & Security (NFR-04 to NFR-06)
- **NFR-04 (Zero Database Retention):** The system shall store **zero user data** in persistent databases or disk stores. All data exists only in volatile memory.
- **NFR-05 (Ephemeral Caching):** Identical request responses shall be cached in volatile memory for **30 minutes** using SHA-256 hash keys.
- **NFR-06 (Client Session Isolation):** Client state shall use browser `sessionStorage` (purged on tab close) rather than `localStorage`.

### 4.3 Availability & Reliability (NFR-07 to NFR-08)
- **NFR-07 (Search Resilience):** Pipeline execution shall succeed even if the primary search API key is missing, utilizing the zero-cost fallback chain.
- **NFR-08 (Model Failover):** If the primary LLM model rate-limits or returns 404 (`model_not_found`), the system shall fail over to backup models (`gpt-oss-20b` $\to$ `gpt-oss-120b`).

---

## 5. Input & Output Boundary Contracts

### Input Payload Schema (`POST /validate`)
```typescript
interface ValidateRequest {
  idea: string;            // Required: Min 3 chars, max 500 chars
  targetCustomer?: string;  // Optional: Max 200 chars
  problem?: string;         // Optional: Max 300 chars
}
```

### Output Response Contract (`200 OK`)
```typescript
interface ValidateResponse {
  summary: string;
  results: Array<{ title: string; url: string; snippet: string; score: number; angle: string }>;
  confidence: { marketGrowth: { agree: number; total: number }; competitivePressure: { agree: number; total: number } } | null;
  marketOpportunity: { marketSize: string; trends: string[]; segments: Array<{ segment: string; painPoints: string; motivations: string; buyingBehavior: string }>; opportunityScore: number } | null;
  competitors: { competitors: Array<{ name: string; offering: string; positioning: string; estimatedPrice: string; featureBreadth: string; gap: string }> } | null;
  whiteSpace: { summary: string; competitionNote: string; opportunities: Array<{ title: string; why: string; fit: string; evidence: string }> } | null;
  errors: { marketOpportunity?: string | null; competitors?: string | null };
}
```

---

## 6. System Constraints & Assumptions

1. **Groq Free-Tier Rate Limits:** The shared team API key operates under free-tier rate limits (~1,000 output tokens/minute).
2. **Third-Party API Availability:** System availability relies on external availability of Groq and Tavily APIs.
3. **Browser Compatibility:** Frontend UI requires a modern evergreen web browser (Chrome, Firefox, Safari, Edge) with ES6 and CSS Grid support.
