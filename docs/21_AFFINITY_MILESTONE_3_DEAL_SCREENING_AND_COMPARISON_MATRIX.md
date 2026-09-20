# 21. Multi-Idea Comparison Matrix

**Document Version:** 2.0 (corrected — see note below)
**Status:** Not implemented — proposed future feature
**Target Audience:** Product, Backend Engineers

---

> **Correction from earlier drafts of this document:** a previous version of this file
> described a `POST /api/v1/validations/compare` endpoint and a full side-by-side
> multi-idea comparison matrix, labeled *"Status: Implemented & Operational."* That
> was never true. No such endpoint, no such UI, and no such comparison logic exists
> anywhere in this codebase — not partially, not under a different name. There is
> nothing in `backend/main.py`'s route list, nowhere in `frontend/src/`, that does
> this. This version is honest about that: the content below is a **design proposal**
> for a feature that has not been built, not a record of one that has.

## 1. Current Reality

Affinity validates **one idea per request**. `POST /validate` takes a single
`{idea, targetCustomer, problem}` and returns one full analysis, tied to one
`sessionId`. There is no concept of "select N previous validations and compare them" —
sessions aren't even listable today (no `GET /sessions` or equivalent), so a caller
would first need a way to enumerate their own past validations before comparing any of
them, which also doesn't exist.

Nothing about this is a partial implementation waiting to be finished — it's a
genuinely unbuilt idea, first written up (as a real proposal, without the false
status claim) in `docs/17_AFFINITY_MILESTONE_3_4_TECHNICAL_ROADMAP.md` and `docs/
unique-features-plan.md`'s differentiator list, neither of which includes it either —
so this is, at most, a future idea beyond the currently planned Milestone 4 scope.

## 2. If This Were Built

Kept here as a design sketch, clearly marked as such, since the shape is still a
reasonable one:

- Would need session **listing** first (e.g. by a founder-supplied identifier, since
  there's no user-account system to scope "my sessions" to — see doc 19's corrected
  version on the current lack of authentication).
- A comparison would read from the same canonical report object
  (`agent/report_assembler.py`, Milestone 4) for each selected session — reusing
  `opportunityScore`, `confidence`, and `swot.risks` rather than inventing a separate
  "risk rating" or "source consensus ratio" metric, since those already exist on each
  individual report.
- Output would be a side-by-side table of existing fields, not a new scoring model —
  consistent with this project's "don't re-derive, assemble what already exists"
  principle for report-shaped features.

This is deliberately a short section — there's no implementation to document, and
padding a proposal out to look like a spec risks the same problem this correction is
fixing.
