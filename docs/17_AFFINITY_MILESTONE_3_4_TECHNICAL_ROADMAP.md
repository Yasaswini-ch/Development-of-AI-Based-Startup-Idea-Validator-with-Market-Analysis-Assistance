# 17. Future Technical Roadmap & Milestones 3 & 4 Specifications
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Feature Specification (original plan) — delivery status added 2026-09-26  

---

> **Delivery status (2026-09-26).** This file is the original forward-looking plan. The
> table below records what actually shipped, so it isn't read as a list of things that
> don't exist yet. Where the shipped design differs from the plan, the shipped design
> wins; see the linked docs.
>
> | Planned item | Status | Where it actually lives |
> |---|---|---|
> | 2.1 PDF dossier export | ✅ Built (ReportLab, `GET /validate/{id}/pdf`, `POST /export-pdf`); no grid graphic or citation index | [doc 20](20_AFFINITY_MILESTONE_3_PDF_DOSSIER_EXPORTER_AND_REPORTS.md) |
> | 2.2 Idea comparison matrix | ✅ Built, differently: compares 2–5 **already-validated** sessions (`POST /reports/compare`), no parallel re-runs; plus a Dashboard comparison tab | [doc 21](21_AFFINITY_MILESTONE_3_DEAL_SCREENING_AND_COMPARISON_MATRIX.md) |
> | 2.3 Pitch deck outline generator | ⏳ Not built | — |
> | 3.1 Accounts & saved history | ✅ Built: email + password JWT accounts on Postgres/SQLAlchemy. No OAuth/SSO, no team workspaces | [doc 19](19_AFFINITY_MILESTONE_3_POSTGRESQL_AUTH_AND_DATA_PERSISTENCE.md) |
> | 3.2 Competitor tracking webhooks | ⏳ Not built | — |
> | 3.3 Incubator API portal | ⏳ Not built; the **admin analytics dashboard** part shipped as Platform Health | [doc 22](22_AFFINITY_MILESTONE_5_ANALYTICS_DASHBOARDS_AND_ACCESS_CONTROL.md) |
> | 4 Prisma schema preview | Superseded by the SQLAlchemy tables in `backend/agent/db.py` | [doc 19 §2](19_AFFINITY_MILESTONE_3_POSTGRESQL_AUTH_AND_DATA_PERSISTENCE.md#2-database-schema) |

## 📑 Document Table of Contents
- [1. Executive Summary & Strategic Architecture](#1-executive-summary--strategic-architecture)
- [2. Milestone 3 Engineering Specifications](#2-milestone-3-engineering-specifications)
- [3. Milestone 4 Engineering Specifications](#3-milestone-4-engineering-specifications)
- [4. Architectural Migration Path](#4-architectural-migration-path)

---

## 1. Executive Summary & Strategic Architecture

With **Milestones 1 & 2 complete and verified operational**, Affinity currently delivers real-time web retrieval, LLM market opportunity analysis, local spaCy NER competitor extraction, 3x3 positioning grids, Cross-Source Agreement metrics, and 0–100 Opportunity Scoring.

Milestones 3 and 4 expand Affinity into a enterprise-ready venture screening platform:

```mermaid
flowchart LR
    M1M2["Milestone 1 & 2 (Current)\nHybrid Pipeline + React UI"] --> M3["Milestone 3 (Planned)\nPDF Export + Idea Comparison + Pitch Decks"]
    M3 --> M4["Milestone 4 (Planned)\nUser Accounts + Webhooks + Incubator API"]
```

---

## 2. Milestone 3 Engineering Specifications

### 2.1 One-Click Validation Dossier PDF Export
- **Objective:** Enable founders to export a formatted validation dossier for investor meetings.
- **Implementation:** Backend endpoint `POST /export/pdf` using ReportLab or Puppeteer headless rendering.
- **Contents:**
  - Executive Pitch & 0–100 Opportunity Score Badge.
  - Source Agreement Consensus Metrics.
  - 4 Customer Segment Profiles Table.
  - 3x3 Competitor Positioning Grid Graphic.
  - Citations and Web Source Evidence Directory.

### 2.2 Side-by-Side Startup Idea Comparison Matrix
- **Objective:** Allow founders to submit 2 or 3 competing startup concepts and compare their viability.
- **Frontend UI:** Dual-column dashboard view comparing Opportunity Scores, market sizes, competitor counts, and white-space gap counts.
- **Backend Routing:** Asynchronous `POST /compare` executing parallel LangGraph state graph instances using Python `asyncio.gather()`.

### 2.3 Automatic Pitch Deck Outline Generator
- **Objective:** Convert validation results into a 10-slide Pitch Deck Outline.
- **Slide Mapping:**
  - *Slide 1:* Title & One-Liner Pitch
  - *Slide 2:* Problem Statement & Customer Pain Points
  - *Slide 3:* Market Opportunity (TAM/SAM/CAGR)
  - *Slide 4:* Target Customer Segments & Buying Behaviors
  - *Slide 5:* Competitor Landscape & 3x3 Grid
  - *Slide 6:* White-Space Differentiation

---

## 3. Milestone 4 Engineering Specifications

### 3.1 Authenticated Workspaces & Saved Validation History
- **Objective:** Provide persistent user accounts for incubators, VC firms, and serial entrepreneurs.
- **Database Layer:** PostgreSQL database with Supabase / FastAPI SQLAlchemy ORM integration.
- **Authentication:** JWT (JSON Web Tokens) with OAuth2 Google/GitHub SSO.

### 3.2 Automated Monthly Competitor Tracking Webhooks
- **Objective:** Continuously monitor competitors discovered in validated startup dossiers.
- **Engine:** Monthly cron job scheduled via Celery / Redis workers running spaCy NER against fresh news query angles.
- **Alert Channels:** Email summaries and Slack/Discord webhooks alerting founders when a competitor updates pricing or launches new features.

### 3.3 University & Incubator API Portal
- **Objective:** Allow university pitch competitions to embed Affinity directly into student submission portals.
- **Features:** Developer API Keys, rate-limit tiers, custom white-label reports, and administrative analytics dashboards.

---

## 4. Architectural Migration Path

```typescript
// Milestone 4 Database Entity Preview (PostgreSQL / Prisma Schema)
model IdeaValidation {
  id              String   @id @default(uuid())
  userId          String
  idea            String
  targetCustomer  String?
  problem         String?
  opportunityScore Int
  summary         String
  createdAt       DateTime @default(now())
  
  // Relations
  sources         Source[]
  competitors     Competitor[]
}
```
