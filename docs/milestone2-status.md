# Milestone 2 — Status &amp; Who Starts When

**Last updated:** Sept 3, 2026 (after the null-state UI/positioning grid and the Groq
retry fix landed)

This replaces confusion about "is it my turn yet" — read your name, check your row, start
immediately if it says so. Full task detail is still in
[`milestone2-plan.md`](milestone2-plan.md); this doc is just the current state + the
unblock order.

---

## TL;DR

| Person | Original task | Status | Start now? |
|---|---|---|---|
| Yasaswini | Market Opportunity + Competitor agents | ✅ Done | — |
| Yalene | Orchestration wiring (partial-failure handling) | ✅ Done, merged to `staging` today | — |
| Sashi | Opportunity Score | ✅ Done | — |
| Sashi | Positioning fields (`estimatedPrice`/`featureBreadth`) | ✅ Done | — |
| **Sashi** | **Confidence Indicator** | ❌ Not started | **Yes — start now, zero blockers** |
| Anu | Null/"unavailable" section UI | ✅ Done (filled in ahead of Anu so Varshini wasn't blocked) | — |
| Anu | Positioning grid (2×2 chart) | ✅ Done (same fix) | — |
| **Varshini** | Partial-failure verification | ❌ Not started | **Yes — unblocked, nothing left in your way** |
| Varshini | Error-state UI verification | ❌ Not started | **Yes — unblocked now that the null-state UI exists** |
| Varshini | Cross-industry validation report | ❌ Not started | Can draft now, but see quota note below |

---

## What's done (no action needed)

- **Market Opportunity Agent** (`backend/agent/market_agent.py`) — all 4 segment fields
  populate correctly, with safe fallback text if a field is missing.
- **Competitor Discovery Agent** (`backend/agent/competitor_agent.py`) — returns real
  competitors grounded in search results, empty array (not fabricated data) when none
  found, and already includes `estimatedPrice`/`featureBreadth` (this was technically a
  Phase 2 item and it's already done).
- **Opportunity Score** (`backend/agent/opportunity_score.py`) — implemented, with
  documented edge-case handling ([opportunity-score-edge-cases.md](../backend/agent/docs/opportunity-score-edge-cases.md)).
- **Orchestration wiring** (`backend/agent/graph.py`, `backend/main.py`) — merged to
  `staging` today. Each node now catches its own failures, sets `errors.<node>`, and the
  `/validate` response returns partial data instead of a hard 500. **Verified live**: I ran
  the pipeline and both agents actually hit a real Groq rate-limit error, and the pipeline
  degraded gracefully exactly as designed.
- **Null-state UI + positioning grid** (`MarketOpportunity.jsx`, `CompetitorAnalysis.jsx`,
  `ValidationResults.jsx`) — this was Anu's blocked item; filled in directly so Varshini
  wasn't stuck waiting. Each section now shows an inline "analysis wasn't available"
  message (with the real `errors.<node>` text) when the backend returns `null`, distinct
  from a genuine empty result. Also added the price/feature-breadth positioning grid.
  **Verified live** against a mocked partial-failure response in the browser.
- **Groq rate-limit retry** (`backend/agent/llm.py`) — every LLM call now retries once
  using Groq's own suggested cooldown before giving up. Doesn't fix a fully exhausted
  team-wide quota, but absorbs single transient rate-limit hits that previously went
  straight to fallback content. See the quota note below for what this does and doesn't
  solve.

---

## Start now — in this order

### 1. Sashi — Confidence Indicator (start immediately)
This has **zero dependencies** on anyone else's work — it only needs data that already
exists from Milestone 1's `retrieval.py`. It should have been first, so it's the most
overdue item right now.

- Backend: new `backend/agent/confidence.py` (or a function in `graph.py`) that
  aggregates per-source agreement into something like `{"marketGrowth": {"agree": 3,
  "total": 5}}`, added to the pipeline state and the `/validate` response as `confidence`.
- Frontend: a small standalone badge component near the summary — doesn't touch existing
  layout.
- **No coordination needed with anyone else before starting.**

### 2. Varshini — everything is unblocked now, start today
Both things that were blocking you have landed:

- **Partial-failure verification** — force each node (`market_opportunity`,
  `competitor_discovery`) to raise, and confirm the pipeline still returns 200 with the
  other agent's data intact and `errors.<node>` populated correctly. Do this for both
  nodes.
- **Error-state UI verification** — the null-state UI now exists for real, so you can
  verify against it directly: force a node failure and confirm the frontend shows the
  correct inline "unavailable" message (not a blank section or a crash).
- **Cross-industry validation report** — draft the template and pick your 3 ideas now,
  but see the quota note below before running the real 3-industry test pass, or your
  results may still be rate-limited fallbacks instead of real agent output.

### 3. Anu — nothing outstanding from this list right now
Both the null-state UI and the positioning grid were completed directly to unblock
Varshini. Worth a quick look over the diff to make sure it matches how you'd have built
it — it's a straightforward addition, not a redesign, but you own this component going
forward.

---

## ⚠️ Note on the shared Groq API quota

The team's Groq API key is on the free tier (8000 tokens/minute) and has been getting
exhausted from testing. `agent/llm.py` now retries once against Groq's own suggested
cooldown when it hits a rate limit — this fixes a single transient hit (one request
briefly over the limit), but does **not** fix the whole team's quota being exhausted at
once, since the retry waits at most 30 seconds and the quota may still be gone when it
retries.

A same-request fallback to a second LLM provider (Gemini) was tried and dropped — tested
directly against the live API, it hangs for minutes instead of failing fast, which would
make a failed request worse, not better.

**This still matters most for Varshini's cross-industry validation report** — running
the "3 ideas, 3 industries" test while the quota is exhausted will produce fallback
content, not a real assessment of output quality. Either:
- wait for the per-minute quota to reset before each real test run (slower now that
  fewer failures need a full fallback, but still not instant), or
- ask whoever owns the Groq account to check about a paid tier for the validation day.

---

## Updated timeline (today = Sept 3)

| Day | Focus |
|---|---|
| **Sept 3 (today)** | Orchestration merged. Null-state UI, positioning grid, and Groq rate-limit retry all landed. Sashi starts confidence indicator. Varshini starts partial-failure verification + error-state UI verification (both unblocked) + drafts validation report template/test ideas. |
| **Sept 4** | Sashi finishes confidence indicator. Varshini finishes partial-failure and error-state UI verification. |
| **Sept 5** | Varshini starts cross-industry validation runs (quota permitting). |
| **Sept 6** | Varshini finishes validation report. Whole team: bug bash. |
| **Sept 7** | Buffer day — final polish, README/architecture doc updates, submission. |

If quota issues push the validation report past Sept 6, that's the one item to flag early
rather than discover on submission day.
