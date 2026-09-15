# Milestone 2 — Status &amp; Who Starts When

**Last updated:** Sept 15, 2026 (Varshini's two remaining items closed — see the
task table and §3; plus the qwen3.8 model-swap fix, verification log check #7).
Previous update Sept 6, 2026 (after the competitor-agent NER rewrite, the
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
| Sashi | Positioning fields (`estimatedPrice`/`featureBreadth`) | ✅ Done, and now actually classified sometimes again (see note below) | — |
| **Sashi** | **Confidence Indicator** | ❌ Not started | **Yes — start now, zero blockers** |
| Anu | Null/"unavailable" section UI | ✅ Done | — |
| Anu | Positioning grid (3×3 chart) | ✅ Done — confirmed still 3×3 (`high/mid/low` × `narrow/moderate/broad`) in `CompetitorAnalysis.jsx`, not reduced to 2×2 | — |
| **Yasaswini** | Partial-failure verification | ✅ Done — verified live this session (see below) | — |
| Varshini | Error-state UI verification | ✅ Done — two deliberate forced-failure runs Sept 15 (`uvicorn-errorcheck.log`); check 5 in verification log | — |
| Varshini | Cross-industry validation report | ✅ Done — `docs/milestone2-validation-report.md` written; includes Varshini's 3 locked ideas (fintech, health, hardware) + team's 4 earlier runs | — |

> **Note on positioning fields:** when Competitor Discovery moved to local NER,
> `estimatedPrice`/`featureBreadth` briefly became *always* `"unknown"` in real
> responses (NER couldn't estimate those the way an LLM could), so Sashi's and Anu's
> 3×3 grid - correctly built - never actually rendered in live use. Fixed in
> `d33effc`: `competitor_agent.py` now pattern-matches $ amounts and feature keywords
> from each competitor's own local text to classify them when there's real textual
> evidence, still `"unknown"` when there isn't. Verified live: the invoicing-app idea
> now shows a real competitor placed in the grid. Most competitors will still land on
> `"unknown"` for one or both fields (the heuristic is honest about not guessing) -
> that's expected, not a regression.

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

### 3. Varshini — both items now done ✅
- **Error-state UI verification** — ✅ done Sept 15. Deliberately corrupted the
  `GROQ_API_KEY` in `backend/.env`, ran backend on `:8001` (logged to
  `backend/uvicorn-errorcheck.log`), submitted the same idea twice. Both runs returned
  `200 OK` with `marketOpportunity: null`, `errors.marketOpportunity` set, and
  `competitors` from NER still populated. Frontend showed the correct inline
  `UnavailableCard` on the Market Opportunity tab; Competitors and Sources tabs
  rendered normally. Full write-up in `milestone2-verification.md` check 5.
- **Cross-industry validation report** — ✅ done Sept 15. Written at
  `docs/milestone2-validation-report.md`. Part I covers the team's four earlier verification
  runs (budgeting, coffee, meal-prep, invoicing — three selected as the distinct-
  industry set). Part II incorporates Varshini's own locked test ideas (fintech bill-
  negotiation, health journaling, consumer hardware smart water bottle) with their B1
  captured results and the competitor-quality degradation pattern that triggered the
  NER investigation. B2/B3 status from the plan mapped to existing verification checks.

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

## Updated timeline

| Day | Focus |
|---|---|
| Sept 3 | Orchestration merged. Null-state UI and positioning grid landed. |
| Sept 3–6 | Competitor Discovery rewritten to local NER (frees quota for Market Opportunity), the real `reasoning_effort` quota fix landed, request caching + submit cooldown added, tabbed results UI replaced the dashboard-tiles layout, positioning grid confirmed 3×3, and a live NER bug (comparison-table snippets losing real competitors) found and fixed. All docs (`README.md`, `backend/README.md`, `docs/architecture.md`, this file) brought back in sync with the code — they had drifted since Sept 3. |
| **Sept 6** | Confidence Indicator implemented and verified live. Yasaswini's partial-failure verification done. |
| **Sept 15** | Error-state UI verification completed (two forced-failure runs, `uvicorn-errorcheck.log`). Cross-industry validation report written (`docs/milestone2-validation-report.md`) incorporating both team verification data and Varshini's locked three-idea test set. All Milestone 2 deliverables complete. Also found and fixed a real production incident the runs surfaced: Groq had deprecated `qwen3.6-27b` entirely — the fallback chain now switches on `model_not_found`, the model config moved to `qwen3.8-27b`, and an invalid-JSON-escape repair was added for the new model's output quirk (verification log check #7, 16/16 regression tests). |
| **Sept 7** | Buffer day — whole team bug bash, final submission polish. (Varshini's items above were completed Sept 15.) |

With Varshini's two items closed, **no Milestone 2 action items remain** on this
list — see [`milestone2-verification.md`](milestone2-verification.md)'s summary
table for the full verified-evidence picture.
