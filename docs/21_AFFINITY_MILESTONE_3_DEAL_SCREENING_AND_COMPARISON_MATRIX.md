# 21. Multi-Idea Comparison Matrix

**Document Version:** 3.0 (updated 2026-09-26 against the `staging` branch)
**Status:** Implemented (backend endpoint + two UIs)
**Target Audience:** Product, Backend Engineers, Frontend Engineers, Examiners

---

> **Revision history.** Version 1 of this file described a `POST
> /api/v1/validations/compare` endpoint marked "Implemented & Operational" before
> anything existed. Version 2 corrected that to "not implemented", which was accurate
> on the day it was written. The feature has **since been built**, so version 2 is now
> wrong. This version describes the shipped feature. Note that the real endpoint is
> `POST /reports/compare`, not the `/api/v1/...` path from version 1.

## 1. What Exists Today

A founder can compare between 2 and 5 of their past validations side by side. There
are two entry points, backed by two different data paths:

| Entry point | Who can use it | Data source | Component |
|---|---|---|---|
| **Account menu → Compare ideas** | Signed-in users | `POST /reports/compare` with session ids | `frontend/src/components/CompareIdeas.jsx` |
| **Account menu → Dashboard → "Comparison matrix" tab** | Signed-in users | `GET /me/analytics` (every idea on the account) | `ComparisonMatrixTab` in `frontend/src/components/AnalyticsDashboard.jsx` |

Neither path re-runs retrieval or any agent. Both read out what each session's pipeline
run already produced, following the project's "assemble, don't re-derive" rule for
report-shaped features.

## 2. Backend: `POST /reports/compare`

```
POST /reports/compare
Body: { "sessionIds": ["<uuid>", "<uuid>", ...] }   // 2 to 5 ids, deduplicated
-> 200 { "reports": [<canonical report>, ...], "missing": ["<expired id>", ...] }
-> 404 { "error": "Fewer than 2 of the given sessions were found or unexpired.", "missing": [...] }
-> 422 on fewer than 2 distinct ids or more than 5
```

- Each entry in `reports` is the same canonical report object `GET /reports/{id}`
  returns (`agent/report_assembler.py`).
- An expired or unknown id goes into `missing` instead of failing the whole request.
  A partial comparison is still returned as long as at least two sessions are valid.
- Rate-limited per IP with the same limit as report/PDF endpoints.
- No auth header is required. Session ids act as capability links (see doc 19 §4.2).

## 3. Frontend: Compare Ideas view (`CompareIdeas.jsx`)

- Ideas are added from **History** with an "Add to compare" button. The selection is a
  small basket in `localStorage` (`frontend/src/lib/compareList.js`, max 5), so it
  survives page changes. It is cleared on sign-in and sign-out so one person's
  selection never shows up for the next person on a shared computer.
- A user can also paste a session id or a full emailed report link; the `?session=`
  parameter is extracted automatically.
- Rows shown for each idea: Opportunity score, Market viability, Confidence, Market
  size, Competitors, Top strength, Top risk, Top MVP feature, GTM positioning.

## 4. Frontend: Dashboard "Comparison matrix" tab

Part of the founder Dashboard (see
[doc 22](22_AFFINITY_MILESTONE_5_ANALYTICS_DASHBOARDS_AND_ACCESS_CONTROL.md)). It
compares **every** idea on the signed-in account at once, with no manual selection:

- Columns: Idea, Score, Market size, Competition, Top risk, Revenue model, Source
  agreement, Recommendation.
- Rows are sorted by Opportunity Score and the best idea is highlighted with a 🏆.
- "Competition" is a label derived by `agent/user_analytics.py`; zero named
  competitors reads as "Unclear" rather than "Low", because an empty search result is
  not evidence of an empty market.
- "Recommendation" is a short deterministic phrase from the score and top risk, not an
  extra LLM call.

## 5. Limits

- Only sessions still inside the 7-day / 200-row session TTL can be compared (see doc
  19 §3). Older ideas drop out of both views.
- The comparison is a side-by-side table of existing fields. There is no separate
  "comparison score" or ranking model beyond sorting by Opportunity Score.

## 6. Tests

- Backend: `/reports/compare` cases in `test_report_assembler.py` and
  `test_end_to_end_pipeline.py`, plus `test_user_analytics.py` for the matrix rows.
- Frontend: `AnalyticsDashboard.test.jsx` covers the Dashboard tabs, including the
  comparison matrix.
