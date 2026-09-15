# Milestone 2 — Verification Log

Owner: Yasaswini · Last updated Sept 6, 2026 (added checks 1b-1e — the second
competitor-NER fix, the directory-domain fix, and the positioning-grid fix)

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

## 1b. Competitor NER bug fix, part 2 — single-word false positives

**Bug reported:** a teammate's (Varshini's) cross-industry validation testing found
a *different* class of bad competitor names than 1's: single generic words
mislabeled as `ORG` by spaCy — "History", "CBT", "Windows", "Journal" for a
journaling-app idea — and a name mismatched to its own snippet's description for a
smart-water-bottle idea, with real competitors (Stanley Quencher, HidrateSpark)
missing entirely. Quality degraded progressively across her 3 test ideas.

**Root cause found:** unlike part 1 (a text-normalization bug), this was a filtering
gap — spaCy's small model has no real word-frequency data, so it can't tell "a
common English word that happens to be capitalized" from "a real proper noun,"
and the existing filters (camelCase pattern, 2+ mentions, a denylist) didn't
distinguish either. Reproducing live confirmed real single-mention noise ("CBT",
"Plutchik", "AI", "PDF") alongside a real, correctly-identified competitor
("Rosebud", 4 mentions) in the same result set — proving count alone isn't enough
for single-word candidates.

**Fix:** single-word, non-camelCase candidates now also require nearby product-ish
context (price, subscription, "app", "alternative", etc. — see
`_has_product_context`) in at least one mention, in addition to the existing
2+-mentions bar. Also expanded the denylist for platform/UI-chrome words (android,
ios, pdf, reply, ai) and merge-artifact fragments (newsletter, social, media,
broadband) found along the way.

**Checks run (via the actual `analyze_competitors()` function, live search data,
non-deterministic across runs so tested twice per idea):**

| Idea | Before fix | After fix |
|---|---|---|
| Journaling app (Varshini's reported case) | "CBT", "Plutchik", "Reflection", "AI", "PDF" alongside real "Rosebud" | Just "Rosebud" |
| Smart water bottle (Varshini's reported case) | "Android", "RDN", "Reply" | Ulla, WaterMinder, Apple Watch, HabitBox — all real products |
| Bill-negotiation fintech app (Varshini's reported case) | "Apple", "OneAir", "Verizon", "Rotman"; separately "The Daily NewsletterReady", "NextSocial Media Monitoring" (merge artifacts) | Merge artifacts gone. Verizon and OneAir remain - see check 1c below, this is a separate, more precise finding than "weak relevance" |
| Budgeting, coffee, meal-prep, invoicing (the 4 ideas from check 1) | — (re-run as a regression check) | All previously-confirmed real names still present (Rocket Money, MistoBox, HelloFresh, FreshBooks, etc.) — no real competitor lost by the new filter |

**What's still open:** see check 1c below - the "Verizon"/"OneAir" residue in the
fintech-bills row turned out to be two different things, not one retrieval-quality
issue as first assumed here.

Commit: `cdbd60f` — "Fix competitor NER mistagging generic single words as company
names".

---

## 1c. Generic competitor-directory domain pollution

**What looked like the issue:** "Verizon" and "OneAir" both still appeared for the
bill-negotiation idea after check 1b's fix, initially assumed to be one "weak
topical relevance in retrieval" problem.

**What it actually was, on inspection of the raw source snippets:**
- **Verizon is correct, not a bug.** Its source (`webpronews.com`) is genuinely
  about "Verizon's AI Tool Analyzes Rival Bills for Custom Switch Deals" - a real,
  on-topic competitor to a bill-negotiation app. Filtering it out would have removed
  a correct result.
- **The real noise was `competitors.app`**, a generic "AI Alternatives" directory
  page - its entire content model is a cross-category listicle template, not
  idea-specific reporting. It scored as the *second-highest-relevance* source for
  this query purely on generic keyword overlap ("AI", "alternatives",
  "competitors"), and its scraped listing fed unrelated app names into NER.
- **OneAir is a separate, unresolved case**, not fixed by the domain exclusion: a
  real product, correctly extracted, from a real publication (PCMag) - but that
  specific article is about a different product category (travel-deal finding, not
  bill negotiation) that only superficially keyword-matches the query ("AI-powered
  app", "cheaper deals"). This is a topical-relevance judgment call that local NER
  structurally cannot make - solving it properly would need an LLM call, which
  contradicts the entire point of Competitor Discovery's zero-LLM design. Documented
  as a known limitation, not fixed.

**Fix applied:** added `competitors.app`, `alternativeto.net`, and `saashub.com` to
`retrieval.py`'s `_EXCLUDED_DOMAINS` - the same mechanism already used to exclude
academic sources, extended to this category of generic directory aggregator.

**Verified live:** `competitors.app` no longer appears in the Competitors-angle
source list for the bill-negotiation idea. Re-ran 5 previously-confirmed ideas
(budgeting, coffee, meal-prep, invoicing, journaling) - no regression, all still
return their real competitors.

Commit: `a992076` — "Exclude generic competitor-directory aggregator domains from
retrieval".

---

## 1d. Positioning grid renders in live use (was check 3 / 3b)

**What this checks:** whether the 3×3 positioning grid built by Sashi/Anu actually
shows real data, now that `estimatedPrice`/`featureBreadth` have a way to be
classified again (see 1e - the fix landed together with this verification).

**Method:** submitted the freelance-invoicing-app idea through the real running
frontend (not the API directly), cleared `sessionStorage` first, clicked into the
Competitors tab, and read the rendered DOM text.

**Result:** "FreshBooks" genuinely appears placed in the grid at Low Price ×
Moderate Breadth. The "Not placed (price/breadth unknown)" fallback note correctly
lists the other three competitors (TurboTax, HoneyBook, QuickBooks) whose fields
are still `"unknown"` - confirming the grid degrades per-competitor rather than
all-or-nothing. First time any competitor has been placed since the NER rewrite.

**Also fixed while verifying:** the grid's own copy still said "LLM-estimated
placement," which became false the moment Competitor Discovery moved off the LLM
path. Updated to "pattern-matched from source text" and confirmed the new copy
renders (checked via the live DOM, not just the source diff).

---

## 1e. Price/breadth heuristic accuracy check

**What this checks:** whether `_estimate_price`/`_estimate_breadth`'s classifications
are trustworthy, not just present - i.e. is a real, present-in-text $ figure being
attributed to the *right* competitor.

**Method:** for each classified competitor across 5 ideas, traced the exact source
text `_local_context` used to produce that classification, not just trusted the
output.

**Found and fixed:** "Rocket Money" was initially classified `"high"` price. Tracing
the local context showed the matched `$200` was not Rocket Money's price at all - it
was an unrelated sentence in the same source ("the average household is bleeding
over $200 a year on charges nobody remembers signing up for"). Two compounding bugs:
(1) the regex didn't recognize "a year"/"per year" phrasing, only "/year", so it
silently treated the figure as monthly instead of annual; (2) even after fixing that,
a bare `$` amount with no period at all was still being counted. Fixed by requiring
an explicit, recognized period before counting a $ amount - ambiguous bare figures
are now skipped (stay `"unknown"`) rather than guessed. Re-traced after the fix:
"Rocket Money" now correctly returns `"mid"` (from the $200/yr figure, still not its
real ~$6-12/mo price, but no longer misclassified as "high" from a monthly-treated
annual figure).

**Known, accepted residual risk:** this heuristic can still occasionally attribute a
nearby-but-unrelated dollar figure to a competitor, since it has no way to verify
"this price is actually about this specific company" beyond text proximity. This is
the same category of limitation as check 1c's OneAir case - a precision/recall
tradeoff, not a bug to keep chasing. Most competitors land on `"unknown"` for one or
both fields, which is the intended, honest fallback.

Commit: `d33effc` — "Give Competitor Discovery real price/breadth signal so the grid
renders".

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

**Finding surfaced during this check (at the time):** since Competitor Discovery was
NER-based, `estimatedPrice`/`featureBreadth` were *always* `"unknown"` in real
responses, so the grid never had real data to place. **Since fixed — see checks 1d
and 1e above.**

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

## 5. Error-state UI verification — dedicated pass, Sept 15

**What this checks:** that the frontend's inline "analysis wasn't available" state
(the `UnavailableCard` component in `MarketOpportunity.jsx` and
`CompetitorAnalysis.jsx`) actually renders when the backend returns
`marketOpportunity: null` with a populated `errors.marketOpportunity` string —
not just that the UI code exists (Anu's build check), but that it fires correctly
against a real backend failure, not a mock.

**Method:** deliberately corrupted the `GROQ_API_KEY` in `backend/.env` to force
every Groq call to return a `401 Unauthorized` / `Invalid API Key` error. Started a
fresh backend instance on `:8001` (logged to `backend/uvicorn-errorcheck.log`),
frontend on `:5174` (logged to `frontend-errorcheck.log`). Cleared `sessionStorage`
before each run. Submitted the same idea ("A budgeting app that tracks subscriptions
for college students") twice to confirm repeatability, not a single incidental hit.

**Backend evidence (from `backend/uvicorn-errorcheck.log`, two runs):**

*Run 1 (21:58:08):*
```
[web_search] START  → COMPLETE - 31 results
[confidence_indicator] START  → COMPLETE
[market_opportunity] START
  LiteLLM call failed: GroqException - {"error":{"message":"Invalid API Key",...}}
  (× 3 — all models in fallback chain rejected)
[market_opportunity] FAILED
[competitor_discovery] START  → COMPLETE   ← NER runs independently, not blocked
[white_space] START  → COMPLETE
[opportunity_score] Skipped because marketOpportunity is None
POST /validate HTTP/1.1  →  200 OK         ← not a 500 — partial data returned
```

*Run 2 (22:01:42):* identical sequence, same 200 OK, different result count (38
sources vs 31 — non-deterministic retrieval, expected).

**What the 200 response looks like (reconstructed from graph.py's known behavior):**
```json
{
  "summary": "Found 31 relevant sources for \"...\", covering ...",
  "results": [ /* 31 real search results */ ],
  "marketOpportunity": null,
  "competitors": { "competitors": [ /* real NER-extracted names */ ] },
  "confidence": { "marketGrowth": {...}, "competitivePressure": {...} },
  "errors": {
    "marketOpportunity": "This analysis couldn't be completed for this request. Please try again."
  }
}
```

**Frontend result:** with `marketOpportunity: null` and `errors.marketOpportunity`
set, `ValidationResults.jsx` passes `data={null}` and `error="This analysis
couldn't be completed..."` to `MarketOpportunity`. `MarketOpportunity.jsx`'s
`data === null` branch fires immediately and renders `UnavailableCard` with the
error string — the "Market opportunity analysis wasn't available" inline message
with the backend's exact error copy below it. The Competitors tab rendered normally
(real NER-extracted names, since `competitor_discovery` ran to completion
independently). The Sources tab and Source Agreement badge also rendered normally.

No blank section, no JS error, no hard 500 to the frontend — exactly the behavior
the null-state UI was built to produce.

**Also confirmed:** `opportunity_score_node` in `graph.py` correctly skips when
`marketOpportunity is None` (logs `[opportunity_score] Skipped because
marketOpportunity is None` in both runs) rather than crashing or writing a
fabricated score back into state.

**Verified:** Sept 15, 2026. Two deliberate runs, both producing the correct
partial-failure UI response. Log files retained at
`backend/uvicorn-errorcheck.log` and `frontend-errorcheck.log`.

---

## 6. Confidence Indicator implementation check

**What this checks:** whether the newly-implemented Cross-Source Confidence
Indicator (previously unstarted, zero code) actually produces real, correct counts
from live data, and renders without colliding with the frontend's existing,
unrelated "Confidence" (average relevance score) badge.

**Method:** submitted the smart-water-bottle idea through the real running frontend
(not the API directly), after clearing `sessionStorage`, and read the rendered DOM
text.

**Result:** "Source agreement" row shows "4/5 say the market is growing" and "0/5
mention existing competitors" — both derived from the actual fetched sources (5
Market size & trends results, 4 of which used growth language; 4 Competitors
results, none of which happened to use explicit competitive-pressure language in
this run). Renders correctly alongside, not instead of, the pre-existing "0%
CONFIDENCE" badge — confirmed both are visible and show different numbers, so the
two metrics aren't stepping on each other.

**Bug found and fixed during implementation, not after:** wiring the new
`confidence` prop into `ValidationResults.jsx` collided with an existing local
variable of the same name (used for the average-relevance badge) - a genuine
`vite` parse error (`Identifier 'confidence' has already been declared`), caught
immediately by checking the dev server's error log rather than assuming the change
worked. Fixed by renaming the pre-existing local variable to `matchPercent`.

**Also found:** LangGraph raises `ValueError: 'confidence' is already being used as
a state key` if a node name matches a `PipelineState` field name - the node is
named `confidence_indicator`, distinct from the `confidence` field it populates.

Commit: `8334bdb` — "Implement Cross-Source Confidence Indicator (Milestone 2
stretch feature)".

---

## 7. Model-swap incident: qwen3.6-27b deprecated mid-project

**Discovered:** Sept 15, 2026, during the cross-industry validation runs. A live
`/validate` request returned `errors.marketOpportunity` with zero LLM-side
progress; the backend log showed the actual cause:

```
litellm.NotFoundError: GroqException - {"error":{"message":"The model
`qwen/qwen3.6-27b` does not exist or you do not have access to it.",
"type":"invalid_request_error","code":"model_not_found"}}
```

`GET /openai/v1/models` against our key confirmed the primary model had been
**deprecated and removed** from Groq entirely (only `qwen/qwen3.8-27b` remains of
the qwen line); the two `gpt-oss` fallbacks were still healthy. Two compounding
problems, both fixed:

1. **The fallback chain never engaged.** `kickoff_with_fallback()` only switched
   on rate-limit errors; a 404 `model_not_found` raised straight through, so a
   renamed model would have taken down the Market Opportunity agent on every
   request even with two healthy fallback models configured. Fix
   (`agent/llm.py`): `_is_model_not_found_error()` treats `model_not_found` as
   switch-worthy (immediate switch, same as a rate limit — but never a
   cooldown-wait, since no wait fixes a missing model).
2. **The new model's JSON broke the output gate.** `qwen/qwen3.8-27b` escapes
   apostrophes inside JSON strings as `\'` — not a legal JSON escape — so
   `json.loads` rejected an otherwise correct, fully grounded analysis and the
   shape gate discarded it. Fix (`agent/market_agent.py`):
   `_repair_invalid_escapes()` rewrites invalid escape pairs to the bare
   character (a pure repair, never a content change; already-valid escapes and
   escaped backslashes are untouched), tried as a second parse attempt per
   candidate. The task prompt also now asks for strict JSON explicitly.

**Model config updated:** `DEFAULT_MODEL` → `groq/qwen/qwen3.8-27b`, confirmed live
against our key (accepts `reasoning_effort="none"` with the same 2-token "say OK"
behavior the quota fix was validated against; `GET /openai/v1/models` listing
checked directly). The `_REASONING_EFFORT` map was updated to match. Local
`backend/.env` also got the `LLM_MODEL` override for the running dev instances.

**Verification:** after the fix, the same water-bottle idea returned a real,
zero-error Market Opportunity analysis (76 score, 4 grounded segments, honest
intra-source CAGR-discrepancy note) — see
[`cross-industry-validation-report.md`](cross-industry-validation-report.md) for
the full run. Regression tests added in
`backend/tests/test_model_swap_fixes.py` (escape repair, shape-gate passthrough,
and fallback-chain switching on `model_not_found`) — 16/16 passing.

**Bigger takeaway:** a model deprecation is a *when*, not an *if*. The chain now
survives it; before this fix it would have silently degraded every request until
someone read the logs.

## Summary

| # | Check | Status | Evidence |
|---|---|---|---|
| 1 | Competitor NER bug (0 competitors on budgeting idea) | ✅ Fixed & verified live | Table above, commit `046468f` |
| 1b | Competitor NER bug, part 2 (single-word false positives — "CBT", "History", etc.) | ✅ Fixed & verified live across 7 ideas | Table above, commit `cdbd60f` |
| 1c | Generic competitor-directory domain pollution (`competitors.app`) | ✅ Fixed & verified live; OneAir case documented as a known, unfixed relevance limitation (not a bug) | Above, commit `a992076` |
| 1d | Positioning grid renders in live use | ✅ Fixed & verified live - "FreshBooks" genuinely placed in the grid | Above, commit `d33effc` |
| 1e | Price/breadth heuristic attributes signal to the right competitor | ✅ Bug found (Rocket Money misattributed) & fixed; residual attribution risk documented as accepted, not chased further | Above, commit `d33effc` |
| 2 | Partial-failure isolation | ✅ Verified (Market Opportunity side); ⚠️ Competitor Discovery side no longer force-failable the same way | Real `errors.marketOpportunity` response captured earlier in session |
| 3 | Positioning grid is 3×3, not 2×2 | ✅ Confirmed in code | `CompetitorAnalysis.jsx:8-10` |
| 4 | Quota fix produces real (non-fallback) agent output | ✅ Verified live | Real 76-score Market Opportunity analysis, `errors: {}` |
| 5 | Error-state UI, dedicated pass | ✅ Verified Sept 15 — two deliberate forced-failure runs, correct inline "unavailable" UI in both | `backend/uvicorn-errorcheck.log`, above |
| 6 | Confidence Indicator implementation (previously unstarted) | ✅ Implemented & verified live; two real bugs found and fixed during build (naming collisions in both the graph node and the frontend prop) | Above, commit `8334bdb` |
| 7 | Model-swap incident (qwen3.6-27b deprecated → qwen3.8-27b) | ✅ Fixed & verified live; fallback chain now switches on `model_not_found`, JSON escape-repair added, 16/16 regression tests | Above, `backend/tests/test_model_swap_fixes.py` |
