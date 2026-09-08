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
| 1b | Competitor NER bug, part 2 (single-word false positives — "CBT", "History", etc.) | ✅ Fixed & verified live across 7 ideas | Table above, commit `cdbd60f` |
| 1c | Generic competitor-directory domain pollution (`competitors.app`) | ✅ Fixed & verified live; OneAir case documented as a known, unfixed relevance limitation (not a bug) | Above, commit `a992076` |
| 1d | Positioning grid renders in live use | ✅ Fixed & verified live - "FreshBooks" genuinely placed in the grid | Above, commit `d33effc` |
| 1e | Price/breadth heuristic attributes signal to the right competitor | ✅ Bug found (Rocket Money misattributed) & fixed; residual attribution risk documented as accepted, not chased further | Above, commit `d33effc` |
| 2 | Partial-failure isolation | ✅ Verified (Market Opportunity side); ⚠️ Competitor Discovery side no longer force-failable the same way | Real `errors.marketOpportunity` response captured earlier in session |
| 3 | Positioning grid is 3×3, not 2×2 | ✅ Confirmed in code | `CompetitorAnalysis.jsx:8-10` |
| 4 | Quota fix produces real (non-fallback) agent output | ✅ Verified live | Real 76-score Market Opportunity analysis, `errors: {}` |
| 5 | Error-state UI, dedicated pass | ❌ Not done — still Varshini's item | — |
