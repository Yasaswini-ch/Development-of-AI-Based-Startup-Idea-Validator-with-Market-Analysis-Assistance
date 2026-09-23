# Track F — Search/Retrieval & Contradiction Detector: Configuration Reference

Track F item 3 (documentation). This documents the two pieces of the pipeline
whose behavior is driven by hand-tuned constants rather than an LLM prompt:
`backend/agent/retrieval.py` (+ `tools.py`) and
`backend/agent/contradiction_detector.py`. Both are read directly from the
current code — nothing here is aspirational or describes a planned future
state.

**Note on `docs/16_AFFINITY_SEARCH_RETRIEVAL_AND_DOMAIN_FILTER.md`:** that
document (marked "Verified & Operational") describes an earlier, simpler
version of the retrieval layer — a flat 5-query list with no query fallback,
no relevance-scoring detail, an abbreviated `_EXCLUDED_DOMAINS` list, and
function names/signatures (`search_tool.run(q)`, `_extract_domain`) that
don't exist in the current code. It has drifted from `retrieval.py`/
`tools.py` as those files evolved. This document is the accurate reference;
whether to update or retire doc 16 is a call for whoever owns that doc suite.

---

## 1. Search/Retrieval (`backend/agent/retrieval.py`, `backend/agent/tools.py`)

### 1.1 Why it's split across two files

`retrieval.py` owns "how do we get good, diverse coverage of one idea" —
turning a single idea/customer/problem submission into several distinct
research angles and merging their results. `tools.py` owns "how do we fetch
and score one query" — it has no idea what an "angle" is. Keeping these
separate means the angle-construction logic doesn't care which search
provider is answering underneath.

### 1.2 Query construction (`build_search_angles`)

Each angle is a `(label, [query, ...fallback queries])` pair — not a single
query. The free-tier search backends (used whenever `TAVILY_API_KEY` isn't
set) are confirmed live to be flaky per exact wording: the same subject can
return zero hits with one extra word and real hits with it removed. Giving
each angle a second, shorter/more generic candidate query gives it another
chance instead of surfacing "no reliable sources" purely because the first
wording didn't happen to match anything that day.

**Subject extraction** (what the query is actually "about"):

- `_compact_subject(idea, max_words=1)` → `prefix`: strips the idea down to
  its lead noun phrase. Concretely: splits at the first `that`/`which`
  clause and keeps only what's before it; strips a leading `AI`/`AI-powered`/
  `artificial intelligence`/`smart`/`intelligent` adjective (looped, so a
  stacked "an AI-powered smart resume tool" strips both); strips a leading
  `a`/`an`/`the`; truncates to `max_words`; trims trailing filler words
  (`_TRAILING_STOPWORDS` — "who", "which", "that", "because", prepositions,
  articles, etc.) so a truncated fragment doesn't end mid-sentence.
- `_distinctive_nouns(idea, max_words=3)`: pulls real `NOUN`/`PROPN` tokens
  out of the idea via the same spaCy model `competitor_agent.py` already
  loads (shared singleton, zero extra load cost), ranked longest-first (a
  cheap specificity proxy) and with generic product/business nouns excluded
  (`_GENERIC_PRODUCT_NOUNS` — "service", "app", "platform", "subscription",
  "kit", "ingredients", "recipe", etc.). This exists because subject
  extraction alone keeps only the *generic* opening noun phrase of a pitch
  like "A subscription box service that delivers ingredients for home
  bartenders to make craft cocktails" — everything domain-specific
  ("cocktails", "bartenders") is in the clause that gets cut. Falls back to
  `[]` if spaCy failed to load (matches `competitor_agent.py`'s own guard).
- `subject` = `prefix` + any distinctive nouns not already in `prefix`.
- `subject_fallback` = `prefix` + at most 1 distinctive noun (shorter,
  second-choice query).
- `short_subject` = `prefix` + at most 1 distinctive noun, used specifically
  for the Customer-demand/How-others-solve-this angles below — DuckDuckGo's
  free tier is an implicit AND across every query term, so combining the
  full `subject` with several customer/problem keywords was confirmed live
  to return zero hits (too many required terms for one page to satisfy).
- `_key_phrase(target_customer/problem, max_words=3/5)`: first few *content*
  words with filler dropped from anywhere in the text (not just the end —
  unlike `_compact_subject`, a free-text sentence like "aged 25-45 who enjoy
  mixology but do not want to buy full bottles" needs filler removed
  throughout, not just at a truncation boundary, or it reads as garbled and
  free providers return zero hits for it).

**The five angles** (first three always fired, last two conditional):

| Label | Primary query | Fallback query | Fired when |
|---|---|---|---|
| Market size & trends | `{subject} market size` | `{subject_fallback} market` | always |
| Competitors | `{subject} competitors alternatives` | `{subject_fallback} competitors` | always |
| Industry news | `{subject} industry news` | `{subject_fallback} news` | always |
| Customer demand | `{short_subject} {customer} demand` | `{prefix} {customer}` | `target_customer` non-empty |
| How others solve this | `{short_subject} {problem_subject} solutions` | `{prefix} {problem_subject}` | `problem` non-empty |

### 1.3 Collection (`collect`)

For each angle, queries are tried **in order**; the first query that returns
any (non-academic) hits wins for that angle and the fallback query is never
tried. Within an angle, results are deduped by `(angle, url)` — **not**
deduped globally across angles. A genuinely relevant source can be real
evidence for more than one research question (e.g. a "best meal planning
apps" roundup is evidence for both Competitors and How-others-solve-this);
collapsing it to a single angle silently emptied out whichever angle lost
the tie-break, even though a matching source existed — it just lived under
a different tab than the one it was evidence for. Final list is sorted by
score, descending, across all angles combined.

`collect_scoped(query, max_results=5)` is a separate, single-query path used
by chat follow-ups — no angle expansion, one query, deduped by URL only.

### 1.4 Domain exclusion (`_EXCLUDED_DOMAINS`, in `retrieval.py`)

Applied via `_is_academic(url)` (checks the hostname, `www.` stripped,
against this set) to every result from every provider, before scoring:

- **Academic/research-paper domains** — read as literature review material,
  not the market/competitor signal a founder needs (per mentor guidance):
  `arxiv.org`, `researchgate.net`, `ssrn.com`, `semanticscholar.org`,
  `jstor.org`, `sciencedirect.com`, `springer.com`, `link.springer.com`,
  `ieee.org`, `ieeexplore.ieee.org`, `pubmed.ncbi.nlm.nih.gov`,
  `ncbi.nlm.nih.gov`, `mdpi.com`, `dl.acm.org`, `wiley.com`,
  `tandfonline.com`.
- **Generic competitor-directory/listicle aggregators** — their content
  model is a cross-category template, not idea-specific reporting, so they
  keyword-match almost any "X competitors and alternatives" query while
  contributing near-zero real signal. Confirmed live: `competitors.app`'s
  generic "AI Alternatives" page scored as the *second-highest-relevance*
  result for an unrelated bill-negotiation-app query purely on "AI"/
  "alternatives"/"competitors" overlap, and its scraped listicle content fed
  unrelated app names into Competitor Discovery's NER step as false
  "competitors": `competitors.app`, `alternativeto.net`, `saashub.com`.

### 1.5 Search providers and scoring (`tools.py`, `fetch_results`)

Tavily first (a real, trained relevance score per result) when
`TAVILY_API_KEY` is set and the call succeeds; otherwise the free fallback
chain runs in order — DuckDuckGo, topped up with Wikipedia if still under
`max_results`, topped up with Hacker News (Algolia) if still under. Each
provider fails independently (caught and logged, not raised) so one
provider being down doesn't block the others.

The free providers don't return their own relevance score, so
`_relevance_score(query, title, snippet)` computes one:

- Keywords extracted from query/title+snippet via a naive stemmer (strips a
  trailing "s" on words longer than 4 chars) and a stopword list
  (`_STOPWORDS` — articles, prepositions, plus generic angle-suffix words
  like "market"/"size"/"growth"/"trends"/"competitors" that would otherwise
  match nearly everything).
- Each matched keyword is weighted by length (`_keyword_weight`, floors at
  0.3, longer word = more weight) — a cheap IDF stand-in with no corpus to
  compute real term frequencies from.
- **Minimum-match gate:** for queries with ≥ 2 keywords, at least 2 distinct
  keywords must match or the score is forced to 0 — closes a specific
  failure mode where one long/heavy incidental word (e.g. "subscription")
  alone crossed the inclusion threshold on an otherwise unrelated page
  (confirmed live: a "Marvel Legends" Wikipedia page scored 0.38 for a
  cocktail-business query purely by sharing "subscription" — a comics
  subscription, not a cocktail one).
- Final score = `weighted_ratio * coverage_ratio`, rounded to 2 decimals.
- **Inclusion threshold: score ≥ 0.3** (`_free_fallback`'s final filter) —
  anything below is dropped before it ever reaches `collect()`.

Wikipedia results are additionally filtered by title shape
(`_WIKIPEDIA_LOW_SIGNAL_TITLE`) to drop list/index/glossary/timeline/
disambiguation pages — structurally never useful for market research
regardless of relevance score (confirmed live: "List of serial killers by
number of victims" surfaced as a "relevant" Competitors-angle result for a
todo-app query via pure keyword overlap).

### 1.6 Tuning surface

Everything above that's a knob rather than fixed logic lives as a
module-level constant: `_EXCLUDED_DOMAINS`, `_GENERIC_PRODUCT_NOUNS`,
`_TRAILING_STOPWORDS`/`_FILLER_WORDS` (retrieval.py); `_STOPWORDS`, the 0.3
inclusion threshold, and the 2-keyword minimum-match gate (tools.py). None
of these were changed as part of this documentation pass — this is a
reference, not a retune.

---

## 2. Contradiction Detector (`backend/agent/contradiction_detector.py`)

### 2.1 What it is and isn't

A local, deterministic post-processing step over artifacts the pipeline has
already computed (market opportunity, SWOT, MVP, GTM) — **not** another LLM
agent, same convention as `white_space.py`/`opportunity_score.py`. It flags
apparent tensions between claims (e.g. "the market is described as growing,
but this segment's buying behavior reads as price-resistant"). It is
explicitly a heuristic, not proof of an actual contradiction — it surfaces
things worth a founder's attention. Every flag carries the `sourceIds` of
the claims it's built from, so it's verifiable the same way any other claim
in the app is.

Wired into the pipeline as the `contradiction_detector` node in `graph.py`
(after `gtm_strategy`), exposed in the `/validate` response under
`contradictions`, capped at `_MAX_CONTRADICTIONS = 6`. A missing upstream
section (`None`, e.g. because that node failed) is treated as "nothing to
check there," not an error — every check tolerates `None` via its own
`or {}`/`or []` defaults, so a partial pipeline failure doesn't take this
node down with it.

### 2.2 The four checks

Each check returns one flag `{"type", "summary", "sourceIds"}` or `None`. No
current check returns more than one flag per artifact set. Signal-word
matching (`_has_any`) is a plain case-insensitive substring test against the
constant tuples below — not NLP, so it's exact-phrase, not synonym-aware.

| # | `type` | Trigger condition | Source of `sourceIds` |
|---|---|---|---|
| a | `marketGrowthVsWeakDemand` | `marketSize`/`trends` text contains a growth signal word **and** at least one segment's `buyingBehavior`/`motivations` contains a weak-demand signal word | dedup of growth-trend claims' `sourceIds` + that segment's `sourceIds` |
| b | `highOpportunityVsHighSeverityRisks` | `opportunityScore >= 70` **and** ≥ 2 SWOT risks rated `severity == "high"` | dedup of the high-severity risks' `sourceIds` |
| c | `premiumPositioningVsPriceSensitiveSegment` | GTM `positioning` text contains a premium signal word **and** at least one segment's `painPoints`/`motivations`/`buyingBehavior` contains a price-sensitive signal word | `positioningSourceIds` + that segment's `sourceIds` |
| d | `broadMvpScopeVsHighEffortLimitedValidation` | ≥ 4 MVP features **and** ≥ half rated `effort == "high"` **and** ≥ half carry no `sourceIds` at all | dedup of every feature's `sourceIds` |

Checks (a) and (c) return on the **first** matching segment found (not every
matching segment) — if multiple segments qualify, only one flag is produced
per check per request, since `detect_contradictions` runs each check once.

### 2.3 Signal-word lists (the tuning surface)

```python
_GROWTH_SIGNALS = ("growing", "growth", "expanding", "rising", "increasing",
                    "booming", "high growth", "rapidly growing")

_WEAK_DEMAND_SIGNALS = ("not clear from the sources", "not clear", "not evident",
                         "unclear", "no clear demand", "limited evidence",
                         "not tested", "unproven")

_PREMIUM_SIGNALS = ("premium", "luxury", "high-end", "upscale", "high-margin")

_PRICE_SENSITIVE_SIGNALS = ("price-sensitive", "price sensitive", "budget",
                             "affordable", "cost-conscious", "cost conscious",
                             "cheap", "low-cost", "low cost")
```

Check (b)'s threshold (`opportunityScore >= 70`, `>= 2` high-severity risks)
and check (d)'s thresholds (`>= 4` features, `>= half` high-effort, `>= half`
unsourced) are inline numeric literals in their respective functions, not
named constants — anyone retuning them edits
`_high_opportunity_vs_high_severity_risks`/
`_broad_mvp_scope_vs_high_effort_limited_validation` directly.

### 2.4 Backward compatibility

`_claim_text`/`_claim_source_ids` accept either the current
`{"text", "sourceIds"}` claim shape or a bare string, so stale/cached data
predating Track A's structured-claim schema doesn't crash this node — same
defensive pattern `MarketOpportunity.jsx`'s own `typeof` guard uses on the
frontend side for the same reason.

### 2.5 Known limitation

Substring matching means a claim phrased without any of the listed signal
words produces no flag even if it means the same thing (e.g. "customers
have not yet demonstrated willingness to pay" won't match
`_WEAK_DEMAND_SIGNALS` as written). This is a deliberate low-risk-of-false-
positive tradeoff (a strict list under-flags rather than over-flags), not an
oversight — worth knowing if a contradiction "should" have been caught but
wasn't.
