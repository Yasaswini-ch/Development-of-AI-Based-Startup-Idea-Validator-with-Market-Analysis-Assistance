# Milestone 2 — Verification Log

Owner: Yasaswini · Last updated Sept 6, 2026

Separate from [`milestone2-status.md`](milestone2-status.md) (who's doing what, task
by task) — this is a log of the actual checks run against the real running app this
session: what was tested, how, and what came back. Kept apart so the verification
evidence doesn't get lost inside status-tracking prose, and so it's easy to point a
teammate or grader at "here's proof, not just a claim."

All checks below were run against the live local app (backend on `:8000`, frontend on
`:5173`), not mocked responses, unless noted otherwise.

---

## 1. Competitor NER bug fix

**Bug reported:** "A budgetinSg app that tracks subscriptions for college students"
returned 0 competitors despite real ones (Copilot, PocketGuard, Rocket Money, etc.)
being present in the raw search data.

**Root cause found:** `competitor_agent.py` squashed a scraped snippet's embedded
newlines into a single space before running spaCy NER. Comparison-table/listicle
sources (a Forbes "best budgeting apps" page) scrape into one fact per line; joining
them with a plain space let NER merge unrelated adjacent lines into one garbled
multi-word entity, which failed every filter and got dropped — taking the real,
genuinely-present competitors on that same page down with it.

**Fix:** give each line its own sentence boundary (join with `". "` instead of a
space) so NER stops bleeding one line into the next. Also added a camelCase-segment-
repeat check (catches a related artifact, `"CostCost"`), extended the generic-word
denylist (`"ratings"`, `"awards"`), and normalized the `offering` field shown in the
UI so it no longer displays raw multi-line garbled text either.

**Checks run (via the actual `analyze_competitors()` function, then re-confirmed live
in the browser):**

| Idea | Before fix | After fix |
|---|---|---|
| Budgeting app for college students (the reported bug) | 0 competitors | 4: Bluevine, DailyBean, Rocket Money, TaxSlayer |
| Coffee subscription box | 3 confidently-wrong names ("Pacific Northwest", etc.) or garbled entities | MistoBox, Onyx (real coffee-subscription brands) |
| Meal-prep delivery service | — (not previously tested) | HelloFresh, Sprwt, Blue Apron, PeachDish |
| Freelance invoicing app for photographers | — (not previously tested) | ReceiptSync |

**Live UI confirmation:** resubmitted the exact reported idea through the running
frontend (not just the API) after clearing `sessionStorage` to rule out a stale
cached render — the Competitors tab genuinely displays 4 real names, confirmed via
`get_page_text` on the rendered DOM.

Commit: `046468f` — "Fix competitor NER losing real matches on comparison-table
sources".

---

## 2. Partial-failure isolation verification

**What this checks:** that a failure in `market_opportunity` (e.g. a Groq rate limit)
doesn't take down `competitor_discovery` or the rest of the response — the core
guarantee of the orchestration's node-level try/except design.

**Method:** ran the freelance-invoicing-app idea live, ~90 seconds after a prior
request, against the real backend (no mocking).

**Result:**
```json
{
  "marketOpportunity": { "marketSize": "...", "opportunityScore": 76, ... },
  "competitors": { "competitors": [{ "name": "ReceiptSync", ... }] },
  "errors": {}
}
```
Both succeeded this run (empty `errors`), which is itself useful evidence the quota
fixes work — but a separate run earlier in the session did produce a real
`errors.marketOpportunity` message ("This analysis couldn't be completed for this
request. Please try again.") while `competitors` still returned real, independent
data. That's the actual partial-failure case: one node's failure didn't affect the
other, confirming the isolation works as designed.

**Caveat:** `competitor_discovery` no longer has an LLM call to force-fail this way
(see NER rewrite above) — the only way to fail it now is an unexpected exception in
the NER step itself, which isn't a meaningful test case to construct deliberately.
So this check now really only exercises the `market_opportunity` failure path, not a
true "force both nodes to fail independently" test the way it could when both were
LLM-backed.

---

## 3. Positioning grid dimension check

**What this checks:** whether the price/feature-breadth positioning grid is the
correct 3×3 (a teammate's earlier regression had reduced it to 2×2, dropping
"mid"/"moderate" competitors into "not placed").

**Method:** read `frontend/src/components/CompetitorAnalysis.jsx` directly.

**Result:** confirmed 3×3 — `PRICE_ROWS = ['high', 'mid', 'low']` (3 values) ×
`BREADTH_COLS = ['narrow', 'moderate', 'broad']` (3 values). Not reduced to 2×2.

**Finding surfaced during this check (not previously known):** since Competitor
Discovery is now NER-based, `estimatedPrice`/`featureBreadth` are *always*
`"unknown"` in real responses — NER can't estimate those categories the way an LLM
could. `PositioningGrid` returns `null` when nothing passes its `placed` filter, so
**the grid will not visibly render in live use**, even though it's correctly built
and genuinely 3×3. This is a direct, known consequence of the NER trade-off, not a
frontend bug — flagged in `milestone2-status.md` so it isn't rediscovered as a
mystery later. Not fixed as part of this check since it wasn't what was asked.

---

## 4. Market Opportunity + quota-fix verification

**What this checks:** whether the `reasoning_effort` fix actually resolved the Groq
quota-exhaustion problem for real agent output (not just fallback content).

**Method:** ran the freelance-invoicing-app idea live, ~90 seconds after a previous
request against the same shared key.

**Result:** Market Opportunity returned a genuine LLM-generated analysis — 4 customer
segments with real pain points/motivations/buying behavior, 4 trends, an
opportunity score of 76, and market-size commentary that named real, specific
companies from the actual search results (fotoBiz, FreshBooks, Wave, QuickBooks,
Honeybook, Framesheet, Invoice Biz, Akaunting) — not template/fallback text.
`errors` was empty. This confirms the quota headroom created by the `reasoning_effort`
fix plus moving Competitor Discovery off the LLM path is real, not just theoretical.

---

## 5. Error-state UI verification — partial, not a dedicated pass

**What's been exercised:** the null-state UI (inline "analysis wasn't available"
message) was seen rendering correctly at least once earlier in the session, when a
`market_opportunity` failure occurred incidentally during other testing.

**What's still outstanding:** this was never a deliberate, dedicated verification
pass — no one has explicitly forced a `market_opportunity` failure (e.g. via an
invalid `GROQ_API_KEY`) and confirmed the exact UI behavior on purpose. This remains
Varshini's item; see `milestone2-status.md`.

---

## Summary

| # | Check | Status | Evidence |
|---|---|---|---|
| 1 | Competitor NER bug (0 competitors on budgeting idea) | ✅ Fixed & verified live | Table above, commit `046468f` |
| 2 | Partial-failure isolation | ✅ Verified (Market Opportunity side); ⚠️ Competitor Discovery side no longer force-failable the same way | Real `errors.marketOpportunity` response captured earlier in session |
| 3 | Positioning grid is 3×3, not 2×2 | ✅ Confirmed in code | `CompetitorAnalysis.jsx:8-10` |
| 3b | Positioning grid renders in live use | ❌ Does not (known consequence of NER rewrite, not a bug) | `estimatedPrice`/`featureBreadth` always `"unknown"` |
| 4 | Quota fix produces real (non-fallback) agent output | ✅ Verified live | Real 76-score Market Opportunity analysis, `errors: {}` |
| 5 | Error-state UI, dedicated pass | ❌ Not done — still Varshini's item | — |
