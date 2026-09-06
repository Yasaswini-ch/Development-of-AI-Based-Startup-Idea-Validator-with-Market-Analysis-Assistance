# Milestone 2 — Status &amp; Who Starts When

**Last updated:** Sept 6, 2026 (after the competitor-agent NER rewrite, the
`reasoning_effort` quota fix, request caching/submit cooldown, the tabbed results UI,
and the 3×3 positioning-grid fix all landed)

This replaces confusion about "is it my turn yet" — read your name, check your row, start
immediately if it says so. Full task detail is still in
[`milestone2-plan.md`](milestone2-plan.md); this doc is just the current state + the
unblock order. For the actual checks run against the live app (what was tested, how,
and what came back) rather than just a status claim, see
[`milestone2-verification.md`](milestone2-verification.md).

---

## TL;DR

| Person | Original task | Status | Start now? |
|---|---|---|---|
| Yasaswini | Market Opportunity + Competitor agents | ✅ Done (Competitor agent later rewritten from LLM to local NER — see below) | — |
| Yalene | Orchestration wiring (partial-failure handling) | ✅ Done, merged to `staging` | — |
| Sashi | Opportunity Score | ✅ Done | — |
| Sashi | Positioning fields (`estimatedPrice`/`featureBreadth`) | ✅ Done (now always `"unknown"` for real responses since the NER rewrite — see note below) | — |
| **Sashi** | **Confidence Indicator** | ❌ Not started | **Yes — start now, zero blockers** |
| Anu | Null/"unavailable" section UI | ✅ Done | — |
| Anu | Positioning grid (3×3 chart) | ✅ Done — confirmed still 3×3 (`high/mid/low` × `narrow/moderate/broad`) in `CompetitorAnalysis.jsx`, not reduced to 2×2 | — |
| **Yasaswini** | Partial-failure verification | ✅ Done — verified live this session (see below) | — |
| Varshini | Error-state UI verification | ⚠️ Partially covered (see below) — worth Varshini's own pass | Can start, low priority |
| Varshini | Cross-industry validation report | ⚠️ Raw test data now available for 4 ideas (see below), report itself not yet written | **Yes — data's ready, write it up** |

> **Note on positioning fields:** since Competitor Discovery is now local NER instead
> of an LLM call, `estimatedPrice`/`featureBreadth` are *always* `"unknown"` in real
> responses (NER can't estimate those the way an LLM could). The 3×3 grid component
> still exists and is correctly wired, but it will only ever render for genuinely
> "unknown"-free data (e.g. hand-crafted test fixtures) — in live use, the grid
> currently won't display because nothing gets classified. This is a direct, known
> consequence of the NER trade-off, not a bug in Sashi's or Anu's work — flagging it
> here so it isn't rediscovered as a mystery later.

---

## What's done (no action needed)

- **Market Opportunity Agent** (`backend/agent/market_agent.py`) — all 4 segment fields
  populate correctly, with safe fallback text if a field is missing.
- **Competitor Discovery** (`backend/agent/competitor_agent.py`) — **rewritten from an
  LLM/CrewAI agent to local spaCy NER**, by explicit decision: it doesn't need an LLM's
  open-ended reasoning, just reliable name-reading off search snippets, and every LLM
  call it used to make was quota the Market Opportunity agent could use instead. Also
  fixed a real bug found via live testing: a scraped comparison-table snippet's
  embedded newlines were bleeding adjacent lines into one garbled entity, which both
  produced garbage names and silently dropped real competitors present in the same
  data (confirmed live: a student-budgeting-app query returned 0 competitors before
  the fix, 4 real ones after — Bluevine, DailyBean, Rocket Money, TaxSlayer). See
  `docs/architecture.md` §2 for the full mechanism.
- **Opportunity Score** (`backend/agent/opportunity_score.py`) — implemented, with
  documented edge-case handling ([opportunity-score-edge-cases.md](../backend/agent/docs/opportunity-score-edge-cases.md)).
- **Orchestration wiring** (`backend/agent/graph.py`, `backend/main.py`) — merged to
  `staging`. Each node catches its own failures, sets `errors.<node>`, and the
  `/validate` response returns partial data instead of a hard 500. **Verified live
  again this session** on the real running app (freelance-invoicing-app idea): Market
  Opportunity's LLM call succeeded with a real 76-score analysis while Competitor
  Discovery (no LLM call to fail) returned its own real result independently —
  confirming both the success path and, from earlier runs, the partial-failure path
  (`errors.marketOpportunity` populated, `competitors` still real data) both work as
  designed. This also serves as **Yasaswini's partial-failure verification** item —
  done directly this session, not by Varshini.
- **Null-state UI + positioning grid** (`MarketOpportunity.jsx`, `CompetitorAnalysis.jsx`,
  `ValidationResults.jsx`) — each section shows an inline "analysis wasn't available"
  message (with the real `errors.<node>` text) when the backend returns `null`, distinct
  from a genuine empty result. The positioning grid is genuinely 3×3, not the 2×2 a
  since-fixed regression had reduced it to. **Note:** as of the NER rewrite, the grid
  won't visibly render in live use since `estimatedPrice`/`featureBreadth` are always
  `"unknown"` now — see the TL;DR note above. Verified live against real (not mocked)
  partial-failure and full-success responses in the browser this session.
- **Groq quota fix, for real this time** (`backend/agent/llm.py`) — the earlier
  "retry once on rate limit" mitigation didn't fix a fully exhausted quota; what
  actually fixed it was discovering that `qwen3.6-27b` reserves a hidden-reasoning
  output-token budget that alone exceeded Groq's ~1000 output-tokens/minute cap.
  Setting `reasoning_effort="none"` (`"low"` for the gpt-oss fallback models)
  eliminates that wasted scratchpad — confirmed directly against the live API and
  through real pipeline runs (fewer failures, sharply fewer tokens per call). Combined
  with moving Competitor Discovery off the LLM path entirely (above), the two agents
  no longer compete for the same tiny per-minute budget. Two smaller mitigations sit
  on top: an in-memory response cache (`main.py`, 30-min TTL, never caches a response
  with any `errors` set) and a 5-second frontend submit cooldown, both just reducing
  redundant/duplicate calls rather than fixing anything structural.

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

### 2. Yasaswini — partial-failure verification, done
- **Partial-failure verification** — ✅ done directly this session, not Varshini's
  item to pick up: a live run against the freelance-invoicing idea returned a real
  `errors.marketOpportunity` message with `competitors` still populated from real
  data, confirming the isolation works. `competitor_discovery` no longer has an LLM
  call to force-fail this way (see the NER rewrite above) — the only way to fail it
  now is an unexpected exception in the NER step itself, which isn't a meaningful
  test case anymore. Nothing further needed here.

### 3. Varshini — two items left
- **Error-state UI verification** — the null-state UI works and was exercised live
  this session, but that was incidental to other testing, not a deliberate UI-focused
  pass. Still worth 30 minutes of your own verification against the real running app
  (force a `market_opportunity` failure — e.g. temporarily set an invalid `GROQ_API_KEY`
  — and confirm the frontend shows the correct inline message, not a blank section).
- **Cross-industry validation report** — real test data now exists for 4 ideas, run
  live against the actual app this session (not mocked): a student-budgeting app, a
  coffee subscription box, a meal-prep delivery service, and a freelance-invoicing app
  for photographers. Each returned real competitors and (for the invoicing case) a
  real Market Opportunity analysis with a genuine 76 opportunity score. This is raw
  material for your report, not the report itself — you still own picking the final
  3 industries, writing up the assessment, and judging output quality against the
  Milestone 2 rubric. See the quota note below — it's now a much smaller risk than it
  was, but not zero.

### 4. Anu — nothing outstanding from this list right now
Both the null-state UI and the positioning grid were completed directly to unblock
Varshini. Worth a quick look over the diff to make sure it matches how you'd have built
it — it's a straightforward addition, not a redesign, but you own this component going
forward.

---

## ⚠️ Note on the shared Groq API quota — much improved, not eliminated

The team's Groq API key is on the free tier and was getting exhausted from testing.
Three changes since the original version of this note substantially fixed the root
cause (not just retried around it):

1. **`reasoning_effort` fix** (`agent/llm.py`) — the real cause of most "Request too
   large" failures was `qwen3.6-27b` reserving a hidden-reasoning output-token budget
   that alone exceeded Groq's output-tokens-per-minute cap. Setting `reasoning_effort`
   explicitly per model eliminates that waste entirely.
2. **Competitor Discovery moved off the LLM path** (local NER instead) — the two M2
   agents no longer split the same tiny per-minute budget; only Market Opportunity
   calls the LLM now.
3. **Request caching + submit cooldown** — cuts down on redundant/accidental-duplicate
   calls hitting the quota in the first place.

A same-request fallback to a second LLM provider (Gemini) was tried and dropped — tested
directly against the live API, it hangs for minutes instead of failing fast, which would
make a failed request worse, not better.

**Net effect for Varshini's cross-industry validation report**: real test runs this
session (4 different ideas) completed with genuine agent output, not fallback content,
including one case with zero prior wait. The risk of hitting an exhausted quota mid-report
is much lower than when this note was first written, but still not zero on a free-tier
key under concurrent team usage — if a run does come back as fallback content, wait
30-60s and retry rather than reporting it as real output.

---

## Updated timeline (today = Sept 6)

| Day | Focus |
|---|---|
| Sept 3 | Orchestration merged. Null-state UI and positioning grid landed. |
| Sept 3–6 | Competitor Discovery rewritten to local NER (frees quota for Market Opportunity), the real `reasoning_effort` quota fix landed, request caching + submit cooldown added, tabbed results UI replaced the dashboard-tiles layout, positioning grid confirmed 3×3, and a live NER bug (comparison-table snippets losing real competitors) found and fixed. All docs (`README.md`, `backend/README.md`, `docs/architecture.md`, this file) brought back in sync with the code — they had drifted since Sept 3. |
| **Sept 6 (today)** | Sashi starts confidence indicator (still zero blockers, still not started). Yasaswini's partial-failure verification is done. Varshini's error-state UI and cross-industry report are the two remaining real action items, with test data for 4 ideas already available for the latter. |
| **Sept 7** | Buffer day — Sashi finishes confidence indicator, Varshini finishes error-state UI check + writes up the validation report, whole team bug bash, final submission polish. |

Confidence Indicator (Sashi) and the cross-industry validation report write-up
(Varshini) are the two items still genuinely not started — flag either one now if
Sept 7 looks tight, rather than at submission time.
