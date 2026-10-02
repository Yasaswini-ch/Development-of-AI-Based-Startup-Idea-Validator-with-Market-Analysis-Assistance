# Proposal: Better Competitor Detection and Confidence Scoring

**Version:** 1.0 · 2026-09-28 (written against the `staging` branch)  
**Status:** **Part 1 implemented 2026-09-28** (team picked Option B + Option C's
Product Hunt/Wikidata pair). See [Implementation notes](#9-implementation-notes-2026-09-28)
at the end. Section 4's S1/S2 confidence-scoring options are still a proposal - the
team has not picked one yet.
**Why now:** review feedback named competitor detection and the confidence score as the
two weakest parts of Affinity, and suggested replacing NER with an API or an LLM to find
more competitors and score and compare them better.  
**Related:** [confidence-and-evidence-scoring-methodology.md](confidence-and-evidence-scoring-methodology.md), [14 Competitor Grid](14_AFFINITY_COMPETITOR_GRID_AND_POSITIONING_PARSER.md), [15 Opportunity Score](15_AFFINITY_OPPORTUNITY_SCORE_MATHEMATICAL_MODEL.md), [known-limitations-and-future-work.md](known-limitations-and-future-work.md)

---

## 1. How it works today (verified against the code)

### 1.1 Competitor detection (`backend/agent/competitor_agent.py`)
1. Search runs one **"Competitors"** angle (`"<subject> competitors alternatives"`),
   among five angles, returning up to ~5–8 results.
2. **spaCy `en_core_web_sm` NER** reads the titles and snippets of *all* retrieved
   results and keeps `ORG`/`PRODUCT` entities that pass a denylist, a mention-count rule
   and a "product context" rule.
3. At most **4** names are kept (`_MAX_COMPETITORS = 4`).
4. Price and feature breadth come from regex near each mention; Gemini fills gaps.
5. In **deep** mode only, one LLM call (`_profile_with_llm`) profiles the names NER found
   (direct/indirect, pricing, strengths, weaknesses, gap) and builds the comparison matrix.
   **The LLM never adds a competitor NER missed.**

### 1.2 How competitors feed the scores
- **Opportunity Score** (`opportunity_score.py`): 30 of 100 points come from the
  **count** of competitors only: 0 → 30, 1 → 24, 2 → 18, 3 → 12, 4+ → 6.
- **Viability Score** `competitionClarity`: the share of competitors whose price and
  breadth are known.
- Barrier to entry, the strategic wedge's "Incumbent Blindspot" (uses the first
  competitor) and the comparison matrix all read the same list.

### 1.3 Confidence (`graph.py`, see the methodology doc)
- **Overall %** = cited sources with search relevance ≥ 0.5 ÷ cited sources.
- Tiles: source coverage, cross-source agreement (≥ 2 sources), direct evidence,
  average relevance, recency.
- The **verdict** gate (`verdict.py`) uses source coverage (falling back to Overall):
  "pursue" requires ≥ 50%.

## 2. What is actually wrong

### 2.1 Competitors
| Problem | Cause | Effect the user sees |
|---|---|---|
| **Misses well-known competitors** | NER can only find names literally written in 5–8 snippets; the small spaCy model misses lowercase, one-word or unusual brand names | "Only 2 competitors" for a crowded market |
| **Occasional false positives** | publishers, platforms and generic capitalised words tagged as ORG; handled with an ever-growing denylist | a news site or "Android" shown as a competitor |
| **Hard cap of 4** | `_MAX_COMPETITORS` | never a full landscape |
| **No relevance check** | NER finds *companies*, not *competitors to this idea* | a payment provider mentioned in passing counts as a rival |
| **Rich comparison only in deep mode**, and only for NER's names | profiling is additive, not discovery | quick-mode reports have generic "gap" text |

### 2.2 Scoring (the part that makes 2.1 matter more)
- **Missing competitors *raise* the Opportunity Score.** Fewer names found → more
  "competition" points. A detection miss therefore reads as "wide-open market". This is
  the single most important thing to fix, because it turns a data-quality problem into
  a confident-looking wrong answer.
- **Count is a poor measure of competition**: 4 small startups and 4 dominant incumbents
  score the same.
- **Confidence measures topical relevance, not agreement or truth.** The label "6/8
  sources agree" implies agreement, but the formula only checks that the sources are
  on-topic. The 0.5 threshold is uncalibrated, and small denominators (2/2 = 100%) look
  as strong as 18/20.
- **Confidence and scores are shown side by side but don't interact**: a 78/100 score
  built on 2 sources looks as solid as one built on 20.

## 3. Options for competitor detection

### Option A: Keep NER, improve retrieval (smallest change)
- More competitor-focused queries: `"<subject> alternatives"`, `"<subject> vs"`,
  `"best <category> apps/tools"`, `"<top competitor> alternatives"` (second hop).
- Upgrade to `en_core_web_md`/`lg` or add spaCy's `EntityRuler` for brand patterns;
  raise the cap to 6–8.
- **Cost:** +2–4 search calls per run (Tavily credits), 0 LLM calls. Bigger spaCy model
  adds ~40–500 MB, which is risky on the 512 MB free instance.
- **Impact:** moderate recall gain; precision still limited; still no relevance judgment.
- **Effort:** small (1–2 days).

### Option B: LLM extraction pass, grounded in search results (recommended)
- One LLM call reads the Competitors-angle snippets (plus the NER candidates as hints)
  and returns a list of competitors, each with: name, why it competes (direct/indirect),
  and the **`src-N` id and quoted phrase where it appears**.
- **Grounding rule, enforced in code:** a name is kept only if it literally appears in
  the cited snippet (same idea as `sanitize_source_ids` and `verification.py`). The model
  can't add names from memory, so no hallucinated competitors.
- Merge with NER results (union, de-duplicated); NER becomes the zero-cost fallback when
  the LLM call fails, so the section never gets worse than today.
- Fold the existing `_profile_with_llm` into this same call, so profiling and discovery
  are one call and quick mode also gets real gaps.
- **Cost:** net +0 to +1 LLM call per run (replaces or merges with profiling), ~1.5–3k
  tokens; adds a few seconds. Uses the shared Groq/Gemini quota, which is the scaling
  bottleneck (see [scaling-options.md](scaling-options.md)).
- **Impact:** high. Understands context ("X is an alternative to Y"), lowercase and
  unusual names, and direct vs. indirect; gives a real, idea-specific comparison.
- **Effort:** medium (3–5 days incl. prompt, validator, tests, updating doc 14).
- **Optional:** let the model return up to 3 "well-known competitors not in the sources"
  in a **separate, clearly labelled "Suggested, unverified"** list that never feeds any
  score. Useful for founders; safe because it's kept apart from the evidence.

### Option C: A company/product data API as a second source
| API | Good for | Cost / access | Caveat |
|---|---|---|---|
| **Product Hunt API** (GraphQL) | software/consumer apps, with taglines and categories | free with a developer token | weak for non-software ideas |
| **Wikidata / Google Knowledge Graph Search API** | established companies, industry and HQ data | free (KG has a daily quota) | misses startups; not "competitor-to-X" aware |
| **Crunchbase / similar** | startups, funding, categories | paid, expensive for a student project | licensing terms |
| **Tavily with a competitor query + LLM (B)** | any domain | already integrated | this is Option B |
- Use: look up the idea's category and pull top products, or **verify and enrich** names
  found by A/B (website, founding year, funding), which also gives a better "size of
  incumbent" signal for scoring.
- **Cost:** 1–3 external calls per run; new API key(s) and quotas to manage.
- **Impact:** high for software ideas, low elsewhere; best as enrichment, not the only
  source.
- **Effort:** medium to high (new integration, auth, caching, fallback).

### Comparison

| | A: better NER | **B: grounded LLM** | C: company API |
|---|---|---|---|
| Recall (finds more) | + | +++ | ++ (software) |
| Precision (right ones) | + | +++ | ++ |
| Relevance to the idea | – | +++ | + |
| Extra cost per run | search credits | ~1 LLM call | API calls / fees |
| Hallucination risk | none | low (enforced grounding) | none |
| Works when LLMs are down | yes | falls back to NER | yes |
| Effort | small | medium | medium–high |

**Recommendation:** **B + the query part of A** now (grounded LLM extraction over better
competitor queries, NER kept as the fallback). Consider **C (Product Hunt)** later as
enrichment for software ideas.

## 4. Options for scoring and confidence

### Option S1: Make competition and confidence scoring defensible (recommended; no new API)
1. **Stop rewarding missing data.** If fewer than 2 competitors are found *and* the
   Competitors angle had weak results, mark competition as **"unknown"** (neutral
   points and a visible "insufficient competitor data" note) instead of scoring it as
   wide open.
2. **Score competition on more than count:** direct vs. indirect (from Option B),
   incumbent strength (e.g. funding/size from C, or "mentioned in N sources"), and
   whether the idea has a stated gap against each. Example: `competition =
   30 − Σ(weight_direct × strength)`, clamped.
3. **Replace the fixed ratio with a sample-size-aware confidence.** Use the Wilson lower
   bound of "good cited sources / cited sources", so 2/2 scores ~34% while 18/20 scores
   ~70%. Same idea, but small samples stop looking certain.
4. **Composite confidence** from signals we already compute: relevance (the current %),
   **source diversity** (distinct domains, not the same site 5 times), cross-source
   agreement, recency, and the verification pass rate. Publish the weights in the
   methodology doc, e.g. 35 / 20 / 20 / 10 / 15.
5. **Rename "sources agree"** to "relevant cited sources" until real agreement is measured
   (S2).
6. **Show confidence with the score**: "Opportunity 72/100 · Low confidence (3 sources)",
   and let low confidence cap the verdict (already partly true for "pursue").
- **Cost:** no new API calls. **Effort:** small to medium (2–4 days incl. tests and doc update).
- **Impact:** high for defensibility in a review; every number becomes explainable.

### Option S2: Measure real agreement with an LLM judge, and calibrate
- For the key claims (market size, growth, top competitors), an LLM (or small NLI model)
  checks each cited source: **supports / contradicts / unrelated**. Agreement then means
  what it says. `verification.py` and `contradiction_detector.py` already do part of this
  and can be reused.
- **Calibrate** the thresholds on a small hand-labelled set (e.g. 20 ideas × their
  sources, labelled by the team) and report accuracy against it: "our confidence label
  matched human judgment X% of the time". That is the strongest answer to "why should I
  trust this score".
- **Cost:** +1–2 LLM calls per run; a day or two of labelling. **Effort:** medium to high.
- **Impact:** highest credibility, but adds quota pressure.

**Recommendation:** **S1 now**; S2's calibration set is worth doing even without the
LLM judge, because it gives the project a measured accuracy number.

## 5. Suggested plan, if the team agrees

| Step | Change | Files touched | Size |
|---|---|---|---|
| 1 | Competition "unknown" instead of max points when detection is thin (S1.1) | `opportunity_score.py`, `viability_score.py`, tests | small |
| 2 | Extra competitor search queries (A) | `retrieval.py` | small |
| 3 | Grounded LLM competitor extraction + merge with NER; fold profiling in (B) | `competitor_agent.py`, `prompts/competitor_*`, tests | medium |
| 4 | Competition score from direct/indirect + strength (S1.2) | `opportunity_score.py`, doc 15 | small |
| 5 | Wilson-bound + composite confidence, relabel "agree" (S1.3–S1.5) | `graph.py`, `ConfidenceDashboard.jsx`, methodology doc | medium |
| 6 | Calibration set + measured accuracy (S2, partial) | `backend/scripts/`, docs | medium |
| 7 | Product Hunt enrichment for software ideas (C) | new module | optional |

Steps 1–2 are safe and quick; 3 is the main change the reviewer asked for.

## 6. Decisions needed from the team

1. **Competitor detection:** B + A (recommended), A only, or C as well?
2. **Scoring:** S1 (recommended), S1 + S2, or leave scoring as it is?
3. Is +1 LLM call per run acceptable, given shared free-tier quota? (If not, B can run
   only in deep mode.)
4. Should "Suggested, unverified" competitors from model knowledge be shown at all?

## 9. Implementation notes (2026-09-28)

What shipped from §3/§5, against `backend/agent/competitor_agent.py` and
`backend/agent/opportunity_score.py`:

- **Option A (better queries):** a second "alternatives"-phrased Competitors search
  query, one extra search call per run (`agent/retrieval.py`).
- **Option B (grounded LLM discovery):** `_discover_with_llm` replaces
  `_profile_with_llm`; see [doc 14 §7](14_AFFINITY_COMPETITOR_GRID_AND_POSITIONING_PARSER.md#7-grounded-llm-discovery-2026-09-28)
  for the full mechanism. Cap raised from 4 to 6. Net LLM-call cost is the same as
  before (it replaces the one deep-mode call, doesn't add one).
- **Option C (company API), Product Hunt + Wikidata only:** `_enrich_with_apis`,
  best-effort and additive (an `enrichment` object per competitor, only when a match is
  found). Product Hunt needs `PRODUCTHUNT_API_TOKEN` (not yet provisioned as of this
  writing) and its query is a best-effort guess at the public GraphQL schema - **verify
  it live once a token exists**, since the exact search-by-name shape isn't documented.
  Wikidata needs no key. Crunchbase (also part of Option C) was **not** built.
- **S1.1 (stop rewarding missing data):** done - zero competitors scores 15/30
  (neutral) unless the Competitors-angle search itself returned enough results to
  trust a confirmed "none found".
- **S1.2 (score more than count):** partially done - a competitor's `classification`
  (direct/indirect, from B) now weights the competition score; incumbent
  size/strength (from C) does not yet feed scoring.
- **S1.3–S1.6 (Wilson-bound confidence, composite confidence, relabeling, showing
  confidence with the score) and S2 (LLM-judged agreement, calibration set):** not
  built. Still open decisions - see §4.

Not yet done: frontend rendering of the new `enrichment` field; updating the
Known Limitations doc's competitor/confidence entry to link here (see §3.4 there,
already added).

Tests: `backend/tests/test_competitor_discovery.py`, `backend/tests/test_competition_scoring.py`.
