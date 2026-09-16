# API Cost, Accuracy, and System Performance Metrics
**Project:** Affinity — AI-Based Startup Idea Validator  
**Document version:** September 2026 · Milestones 1 & 2 (current)  
**Pricing verified:** September 15, 2026 — Tavily and Groq live pricing pages  
**Scope:** Backend pipeline only. Frontend is a static React/Vite build with no direct API spend.

---

## 1. Executive Summary

Affinity's backend pipeline is intentionally **API-frugal by design**. Of the six pipeline nodes that run per request, only **one** (`market_opportunity`) makes a paid LLM call. All other nodes — web search summary, competitor discovery, confidence indicator, white-space analysis, and opportunity score — run locally with zero API cost per request. This section documents what that means in concrete numbers: what is spent per request, what accuracy each node achieves, and how the system performs end to end.

---

## 2. Pipeline Architecture at a Glance

The full request cycle involves two external API categories: **search** and **LLM reasoning**. Each node's cost class is listed below.

| # | LangGraph Node | Module | Cost Class | API Used |
|---|---|---|---|---|
| 1 | `web_search` | `agent/retrieval.py` + `agent/tools.py` | Paid (optional) or Free | Tavily (primary); DuckDuckGo / Wikipedia / HN (fallback) |
| 2 | `confidence_indicator` | `agent/confidence.py` | **Zero** | None — regex over already-fetched text |
| 3 | `market_opportunity` | `agent/market_agent.py` | **Paid (LLM)** | Groq — `qwen/qwen3.8-27b` (primary), `openai/gpt-oss-20b` / `gpt-oss-120b` (fallback) |
| 4 | `competitor_discovery` | `agent/competitor_agent.py` | **Zero** | None — local spaCy `en_core_web_sm` NER |
| 5 | `white_space` | `agent/white_space.py` | **Zero** | None — deterministic post-processing |
| 6 | `opportunity_score` | `agent/opportunity_score.py` | **Zero** | None — weighted arithmetic formula |

> [!IMPORTANT]
> As of Milestone 2, the pipeline makes **at most one LLM call per request** (`market_opportunity`). Web Search was cut from an LLM call to a template in Milestone 1; Competitor Discovery was rewritten from a CrewAI crew to local NER in Milestone 2. A summary-paraphrase LLM call that existed in early Milestone 1 was also removed — it was already producing the deterministic template output most of the time, making the call redundant.

---

## 3. API Cost Breakdown

### 3.1 Search API (Tavily)

| Parameter | Value |
|---|---|
| Provider | Tavily |
| Trigger | `TAVILY_API_KEY` present in `.env` |
| Queries per request | 3 to 5 (one per search angle; see §3.1.1) |
| Results per query | Up to 8 |
| **Free tier** | **1,000 API credits/month** — no credit card required; resets on the 1st of each month |
| **Pay-as-you-go** | **$0.008 per API call** (standard search) — billed only above free-tier usage |
| **Student plan** | **Free** — verified students can apply via Tavily's student account program |
| Fallback (zero cost) | DuckDuckGo + Wikipedia + Hacker News — triggered if Tavily key is absent or call fails |

#### 3.1.1 Search Angles

The retrieval layer expands one idea into up to five distinct angles (from [`agent/retrieval.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/retrieval.py)):

| Angle Label | Query Template | Always Fired? |
|---|---|---|
| Market size & trends | `{idea} market size and growth trends` | Yes |
| Competitors | `{idea} competitors and existing alternatives` | Yes |
| Industry news | `{idea} industry news and recent developments` | Yes |
| Customer demand | `{idea} demand among {targetCustomer}` | Only if `targetCustomer` provided |
| How others solve this | `how startups solve: {problem}` | Only if `problem` provided |

**Minimum per request:** 3 Tavily calls · **Maximum per request:** 5 Tavily calls

#### 3.1.2 Relevance Scoring

When Tavily is not configured, the free fallback computes its own relevance score:

$$\text{score} = \min\left(1.0,\ \frac{|\text{query keywords} \cap \text{result keywords}|}{|\text{query keywords}|}\right)$$

Stopwords (`a`, `the`, `market`, `growth`, `competitors`, etc.) are stripped before comparison. Results are deduplicated by URL (keeping the highest-scoring copy across angles) and returned sorted by score descending.

---

### 3.2 LLM API (Groq)

#### 3.2.1 Model Configuration

Three Groq-hosted models are configured in [`agent/llm.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/llm.py), each with its own separate rate-limit quota bucket:

| Role | Model String | `reasoning_effort` | Free Rate Limit | Input Price | Output Price |
|---|---|---|---|---|---|
| Primary | `groq/qwen/qwen3.8-27b` | `"none"` | ~1,000 output tokens/min | ~$0.29 / 1M tokens *(Qwen3 32B)* | ~$0.59 / 1M tokens |
| Fallback 1 | `groq/openai/gpt-oss-20b` | `"low"` | ~1,000 output tokens/min | ~$0.15 / 1M tokens | ~$0.60 / 1M tokens |
| Fallback 2 | `groq/openai/gpt-oss-120b` | `"low"` | ~1,000 output tokens/min | ~$0.59 / 1M tokens | ~$1.18 / 1M tokens |

> [!NOTE]
> Prices are verified against Groq's live pricing as of September 2026 and are subject to change. The project currently runs on **Groq's free tier** (shared team key) — no dollar charges accrue until that quota is exhausted. Groq also offers a **50% discount for batch/async processing** and **50% off cached input tokens**, neither of which this pipeline currently uses.

> [!IMPORTANT]
> The `reasoning_effort="none"` setting for `qwen3.8-27b` is **critical, not cosmetic**. By default this model reserves a hidden `<think>` scratchpad whose output-token budget alone exceeds Groq's ~1,000 tokens/minute cap, causing "Request too large" failures on every call regardless of input size. Setting it to `"none"` eliminates the scratchpad entirely. The two fallback models reject `"none"` and require `"low"` instead — these values were confirmed by direct API testing, not assumed.

#### 3.2.2 Cost Per Request

The Market Opportunity agent constructs one prompt per request, bounded by:

- **Context window in:** `_MAX_SOURCES_IN_CONTEXT = 10` search results, each snippet capped at `_MAX_SNIPPET_LEN = 300` characters
- **Context window out:** a structured JSON object with `marketSize` (string), `trends[]` (≤4), `segments[]` (≤4 × 4 fields)

**Estimated token usage per request** (measured from real outputs, approximate):

| Component | Tokens (approx.) |
|---|---|
| System / task prompt | ~500–700 input tokens |
| Search context (10 × 300-char snippets) | ~700–1,000 input tokens |
| **Total input** | **~1,200–1,700 tokens** |
| JSON output (marketSize + 4 trends + 4 segments) | ~300–500 output tokens |
| **Total output** | **~300–500 tokens** |

**Dollar cost per successful LLM call** (paid tier, primary model `qwen3.6-27b` ≈ Qwen3 32B pricing):

$$\text{Cost} = \frac{1{,}500 \text{ input}}{1{,}000{,}000} \times \$0.29 + \frac{400 \text{ output}}{1{,}000{,}000} \times \$0.59 \approx \$0.00043 + \$0.00024 \approx \$0.00067\text{ per request}$$

At the **fallback models**: $0.075 input / $0.30 output (gpt-oss-20b) → ~**$0.00033/request**; $0.15 / $0.60 (gpt-oss-120b) → ~**$0.00055/request**.

> [!NOTE]
> At current volumes (a student project on a shared free-tier key), the LLM cost is effectively $0 — it is quota-limited, not dollar-billed. The figures above apply when/if the project migrates to a paid Groq account.

#### 3.2.3 Rate-Limit Fallback Logic

Implemented in [`agent/llm.py`'s `kickoff_with_fallback()`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/llm.py#L104-L162):

```
Primary model → Rate limited? → Switch to fallback 1 immediately (no wait)
Fallback 1   → Rate limited? → Switch to fallback 2 immediately (no wait)
Fallback 2   → Rate limited? → Parse suggested cooldown from error message
                → If cooldown named: wait (capped at 30s), retry once
                → If no cooldown: raise immediately
                → Non-rate-limit error at any step: raise immediately
```

Each model switch is immediate (no wait) because Groq rate-limits **per model**, not per account — each fallback is a genuinely separate quota bucket. A cross-provider fallback to Gemini was tried and reverted after confirming it hangs for minutes past its own timeout parameter rather than failing fast.

---

### 3.3 Zero-Cost Nodes — Cost Breakdown

These nodes produce real, user-visible output with no API spend:

| Node | Method | Cost Per Request |
|---|---|---|
| `confidence_indicator` | Regex scan over already-fetched result text | $0 / 0 tokens |
| `competitor_discovery` | spaCy `en_core_web_sm` NER (loaded once at import time) | $0 / 0 tokens |
| `white_space` | Deterministic combination of market segments + competitor count + top source snippet | $0 / 0 tokens |
| `opportunity_score` | Weighted arithmetic formula over market/competitor outputs | $0 / 0 tokens |

---

### 3.4 Request Caching (Cost Mitigation)

An in-memory cache in [`backend/main.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/main.py) prevents paying for repeat submissions:

| Parameter | Value |
|---|---|
| Cache key | SHA-256 of `{ idea, targetCustomer, problem }` (all lowercased + stripped) |
| TTL | 30 minutes |
| Cache condition | Only stores responses where `errors` contains no truthy values — a partial failure from a rate limit is never cached, so a later retry can actually succeed |
| Storage | In-memory `dict` on the Render instance — intentional, no DB |
| **Cost saving** | A cache hit saves **3–5 Tavily calls** ($0.024–$0.040 on paid tier) and **1 Groq LLM call** (~$0.00067 on paid Qwen3) |

Additionally, the frontend disables the submit button for **5 seconds** after each submission to reduce accidental duplicate API calls while the pipeline is still running.

---

### 3.5 Cost Per Request — End-to-End Estimate

Full cost for one unique validation request (cache miss), assuming **paid Tavily + paid Groq**:

| Component | Calls / Tokens | Unit Price | Cost |
|---|---|---|---|
| Tavily Search (3 angles, minimum) | 3 calls | $0.008/call | **$0.024** |
| Tavily Search (5 angles, maximum) | 5 calls | $0.008/call | **$0.040** |
| Groq LLM — primary model (qwen3.6-27b) | ~1,900 tokens total | ~$0.29 input / $0.59 output per 1M | **~$0.00067** |
| Groq LLM — fallback 1 (gpt-oss-20b) | ~1,900 tokens total | $0.075 input / $0.30 output per 1M | **~$0.00033** |
| Confidence indicator | 0 | Zero-cost local regex | $0 |
| Competitor discovery (NER) | 0 | Zero-cost local spaCy | $0 |
| White-space analysis | 0 | Zero-cost local Python | $0 |
| Opportunity score | 0 | Zero-cost arithmetic | $0 |
| **Total (3 angles, primary model)** | | | **~$0.025** |
| **Total (5 angles, primary model)** | | | **~$0.041** |

**On the free tier (current setup):** $0 in dollar charges. The cost is expressed in quota units — up to 5 of 1,000 free Tavily credits, and some portion of Groq's model-specific per-minute token allowance.

**Caching benefit:** a cache hit on a 5-angle request saves ~$0.041 per re-submission (on paid tier), or ~5 credits on the free Tavily tier.

---

## 4. Accuracy Metrics

### 4.1 Market Opportunity Agent

**Method:** LLM reasoning (Groq) over the top 10 search results.  
**Output validation:** structured JSON shape check after `strip_reasoning()` — every required field of the correct type must be present before the output is accepted.

| Quality Dimension | Mechanism | Notes |
|---|---|---|
| Factual grounding | Prompt explicitly requires every claim to be traceable to the provided sources; hallucination is the model's primary failure mode when sources are thin | "Not clear from the sources" is a valid, expected response for TAM/SAM figures |
| Shape validity | `_is_valid_shape()` + `_is_valid_segment()` checks every field | If shape check fails → `marketOpportunity: null` + `errors.marketOpportunity` message in response |
| JSON extraction | `_find_balanced_objects()` scans brace-balanced substrings, last-to-first, so a valid JSON block is recovered even if the model outputs a visible scratchpad before the real answer | Recovers from "rambling then landing on correct JSON" reliably |
| Segment completeness | All four fields (`segment`, `painPoints`, `motivations`, `buyingBehavior`) are required per segment | A segment missing any one field causes the whole response to fail shape check |
| Output size cap | `trends[:4]`, `segments[:4]` | Prevents token bloat on over-eager model outputs |

**Known failure mode:** if the LLM returns output that validates but where `marketSize` is vague or where all trends lack specific growth signals, the `opportunity_score` node will mechanically score it lower — not a bug, a truthful reflection of weak source signal.

---

### 4.2 Competitor Discovery (NER)

**Method:** spaCy `en_core_web_sm` ORG entity recognition over "Competitors"-angle search snippets.  
**No LLM call — accuracy is deterministic given the same source text.**

#### 4.2.1 Filters Applied (in order)

| Filter | What It Catches | Implementation |
|---|---|---|
| Snippet line normalization | Comparison-table/listicle pages that scrape as one fact per line — naively joining with space caused NER to merge adjacent lines into garbled multi-word entities | Join lines with `". "` to give NER sentence boundaries |
| Entity length | Rejects names > 3 words or < 3 characters | `len(words) > 3 or len(name) < 3` |
| Generic-word denylist | ~40 common non-brand words spaCy's small model mistagged as ORG (`"bank"`, `"android"`, `"pdf"`, `"reply"`, `"history"`, media outlet names, etc.) | `_GENERIC_WORDS` set — extensible as new false positives appear |
| CamelCase merge-artifact check | `"CostCost"` and similar scraped-table artifacts where a repeated column header becomes one entity | `_is_duplicated_merge()` — checks for repeated consecutive camelCase segments |
| Mention count | Multi-word or camelCase names: accept at 1+ mention. Single plain-word names: require 2+ mentions | `_MIN_MENTIONS_WITHOUT_CAMEL_CASE = 2` |
| Product-context requirement | Single plain-word names with 2+ mentions still require nearby product-ish language (`price`, `subscription`, `app`, `alternative`, etc.) in at least one mention | `_has_product_context()` over `ent.sent.text` |
| Near-duplicate deduplication | Drops substring-duplicate name variants, keeping the most-mentioned spelling | `_dedupe_near_matches()` |

#### 4.2.2 Verified Accuracy (Live Tests)

Cross-industry testing results from the Milestone 2 verification pass (see [`docs/milestone2-verification.md`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/docs/milestone2-verification.md)):

| Idea Tested | Real Competitors Identified | False Positives |
|---|---|---|
| Budgeting app for college students | Bluevine, DailyBean, Rocket Money, TaxSlayer | 0 (after both NER fix passes) |
| Coffee subscription box | MistoBox, Onyx | 0 |
| Meal-prep delivery service | HelloFresh, Sprwt, Blue Apron, PeachDish | 0 |
| Freelance invoicing app | ReceiptSync, FreshBooks | 0 |
| Journaling app | Rosebud | 0 (previously: "CBT", "PDF", "Reflection", "AI") |
| Smart water bottle | Ulla, WaterMinder, Apple Watch, HabitBox | 0 (previously: "Android", "RDN", "Reply") |
| Bill-negotiation fintech | Verizon *(correct — their AI bill tool is genuinely on-topic)* | OneAir *(real product, correctly extracted, but off-topic article — accepted known limitation)* |

**Result:** 7 ideas tested live. False positive rate dropped from ~40–60% per idea pre-fix to **0% on 6 of 7 ideas** post-fix. The one residual false positive (OneAir) is a topical-relevance limitation the NER approach cannot resolve without an LLM call — documented and accepted.

#### 4.2.3 Known Limitations

- **`gap` field is generic, not comparative.** NER cannot reason about why a competitor is better or worse than the submitted idea — the field says so explicitly rather than fabricating a comparison.
- **`estimatedPrice` / `featureBreadth` are rough pattern-matches,** not verified pricing data. Both fields stay `"unknown"` when no textual signal is found (the deliberate honest default), and the frontend hides the positioning grid cell for those entries. The heuristic runs only over the 1–2 sentences immediately around a competitor mention, not the whole shared snippet, to avoid attributing one competitor's pricing signal to an adjacent competitor from the same source.
- **Results are non-deterministic across runs** because they depend on live search results, which vary run to run even for identical ideas.

---

### 4.3 Confidence Indicator

**Method:** Regex over already-fetched search result titles and snippets.  
**Output:** per-topic source-agreement counts, not sentiment analysis.

| Dimension | Pattern Matched | What "agree" means |
|---|---|---|
| `marketGrowth` | `growing`, `growth`, `expand`, `increasing`, `rising`, `surge`, `boom`, `CAGR`, `forecast to grow`, `projected to grow` | At least one growth-language word appears in the result's title + snippet |
| `competitivePressure` | `competitor`, `competition`, `competitive`, `alternative`, `rival`, `compete`, `market leader`, `established player` | At least one competitive-language word appears |

**Accuracy note:** two sources both mentioning "CAGR" count as agreement even if one cites 8% and the other cites 20%. This coarseness is deliberate — exact numeric agreement would require extracting and cross-referencing figures, a significantly harder problem than the "source agreement badge" feature warrants solving at regex level. The LLM-based `marketOpportunity.marketSize` field is where numeric synthesis already happens.

---

### 4.4 Opportunity Score

**Method:** deterministic weighted formula.

$$\text{OpportunityScore} = \text{MarketSizeScore}_{/40} + \text{GrowthScore}_{/30} + \text{CompetitionScore}_{/30}$$

| Sub-score | Full Score | Signal Required |
|---|---|---|
| Market size | 40 | Strong signals: `"billion"`, `"large"`, `"global"`, `"rapidly growing"`, `"high growth"` in `marketSize` string |
| Market size | 25 | Medium signals: `"million"`, `"growing"`, `"regional"`, `"expanding"` |
| Market size | 15 | Any non-empty `marketSize` without a "not enough" phrase |
| Market size | 0 | Empty or "not enough data" |
| Growth / trends | 30 | 3+ trends containing growth-positive language |
| Growth / trends | 22 | 2 positive trends |
| Growth / trends | 12 | 1 positive trend |
| Growth / trends | 6 | Trends present but no positive signals |
| Competition (inverse) | 30 | 0 competitors identified |
| Competition (inverse) | 24 | 1 competitor |
| Competition (inverse) | 18 | 2 competitors |
| Competition (inverse) | 12 | 3 competitors |
| Competition (inverse) | 6 | 4+ competitors |

**Fallback behavior (when both LLM agents fail):** rather than returning 0 (which would look like the system ran and found nothing), the node falls back to a weaker score derived from raw search-result count and average relevance score, capped at **50** (since it is weaker signal than real agent analysis). Returns 0 only when there are truly no search results at all.

**Guard against phantom high scores:** if both market agent and competitor agent returned empty outputs (zero trends, zero segments, zero competitors) — the most likely sign of a full Groq rate-limit failure — the formula would otherwise produce an artificially high score (0 competitors = 30/30 "no competition!"). The `_has_no_grounded_data()` check catches this and routes to the search-fallback path instead.

---

## 5. End-to-End System Performance

### 5.1 Latency Profile (Typical Request)

| Stage | Typical Duration | Bottleneck |
|---|---|---|
| Web search (5 angles × up to 8 results) | 1–4 s | Network I/O to Tavily or fallback sources; each angle call uses a 5 s per-source timeout |
| Confidence indicator | < 10 ms | Regex over in-memory text |
| Market opportunity (LLM) | 5–20 s | Groq inference latency; varies by model and current quota pressure |
| Competitor discovery (NER) | 50–300 ms | spaCy NER over up to 40 result texts |
| White-space analysis | < 10 ms | Deterministic Python over already-computed dicts |
| Opportunity score | < 1 ms | Arithmetic formula |
| **Total typical range** | **7–25 s** | Dominated by LLM call; web search is second |

**Pipeline nodes run sequentially** (LangGraph linear graph). A future parallelisation of `market_opportunity` and `competitor_discovery` (which do not depend on each other) could trim total latency by the NER duration, but the gain is small compared to LLM latency and has not been implemented.

### 5.2 Timeout Handling

| Source | Timeout | Behavior on Timeout |
|---|---|---|
| Tavily | Library-managed (typically 5–10 s) | Returns `[]`; DuckDuckGo fallback activates |
| DuckDuckGo | 5 s (`urllib.request.urlopen` timeout) | Returns `[]`; Wikipedia fallback activates |
| Wikipedia | 5 s | Returns `[]`; Hacker News fallback activates |
| Hacker News | 5 s | Returns `[]`; result set is whatever was collected so far |
| Groq LLM | Model-level; `kickoff_with_fallback` switches to next model on rate-limit | On full chain exhaustion: `marketOpportunity: null` + error message in response |

### 5.3 Partial-Failure Behavior

The pipeline is designed so a failure in any single node never crashes the whole request:

| Failure Scenario | HTTP Status | Response Shape |
|---|---|---|
| `web_search` fails entirely (all sources fail) | `502` | `{ "error": "..." }` — the only non-200 outcome |
| `web_search` returns 0 results | `200` | `{ "summary": "...", "results": [] }` — frontend shows `EmptyState` |
| `market_opportunity` LLM call fails (all models exhausted) | `200` | `marketOpportunity: null`, `errors.marketOpportunity: "..."` — all other sections render normally |
| `competitor_discovery` NER raises an unexpected exception | `200` | `competitors: null`, `errors.competitors: "..."` — distinct from `competitors: { "competitors": [] }` (successful run, no names found) |
| `opportunity_score` raises | `200` | `opportunityScore: 0` written into `marketOpportunity` (not propagated as a separate error) |
| `confidence_indicator` / `white_space` raise | `200` | Those fields are missing or default — no separate error surface, since these are post-processing and their failure doesn't degrade the core result |

> [!NOTE]
> The frontend distinguishes `competitors: null` (node failed — shows "analysis unavailable") from `competitors: { "competitors": [] }` (node ran, found no names — shows "no competitors identified in available sources"). These are two different states in the UI, not one.

### 5.4 Caching Hit Rate (Expected Behavior)

- Identical idea + targetCustomer + problem combinations within a 30-minute window → served from cache, **0 API calls**
- The cache key normalizes to lowercase + stripped, so "Smart water bottle" and "smart water bottle" → same key
- Only complete (no-error) responses are cached — a Groq-rate-limited partial failure will be re-attempted on the next request

---

## 6. Quota Management Strategy

### 6.1 Groq Free Tier

The team shares a single free-tier Groq API key. Mitigations layered in order of effectiveness:

| Mitigation | Effect |
|---|---|
| `reasoning_effort="none"` for qwen3.6-27b | Eliminated the biggest single source of token consumption — the model's hidden `<think>` scratchpad was consuming the entire per-minute output token budget before any real output was generated |
| Two-tier fallback (gpt-oss-20b → gpt-oss-120b) | Immediate switch to a separate quota bucket on rate limit — no wait required |
| Competitor Discovery rewritten to local NER | Removed 1 LLM call per request entirely (was previously a full CrewAI crew) |
| Web search summary rewritten to template | Removed 1 LLM call per request entirely (was previously a paraphrase call) |
| 30-minute in-memory request cache | Prevents re-running the pipeline for identical re-submissions |
| Frontend 5-second submit cooldown | Reduces accidental duplicate submissions during testing |

### 6.2 Tavily Free Tier — Capacity and Cost Projections

| Scenario | Monthly Volume | Monthly Cost |
|---|---|---|
| Free tier, 3-angle requests | ~333 validations | $0 |
| Free tier, 5-angle requests | ~200 validations | $0 |
| Paid tier, 3-angle requests | Unlimited | $0.024 × validations |
| Paid tier, 5-angle requests | Unlimited | $0.040 × validations |
| 1,000 validations/month (5 angles) | — | **~$40/month** (Tavily only) |
| 10,000 validations/month (5 angles) | — | **~$400/month** (Tavily only) |

Above the free tier, either upgrade to Tavily's pay-as-you-go plan ($0.008/call) or accept the free fallback chain (DuckDuckGo / Wikipedia / HN) which produces lower-relevance results — the pipeline supports both transparently, controlled by whether `TAVILY_API_KEY` is set.

### 6.3 Groq Cost Projections (If Migrating to Paid)

LLM cost is currently $0 (free tier). At scale on a paid account:

| Monthly Validations | Primary Model (Qwen3) | Fallback 1 (gpt-oss-20b) |
|---|---|---|
| 1,000 | **~$0.67** | ~$0.33 |
| 10,000 | **~$6.70** | ~$3.30 |
| 100,000 | **~$67** | ~$33 |

Groq LLM cost is negligible at the scale this project currently operates at — even at 10,000 validations/month the LLM spend is under $7. Tavily dominates the cost picture by roughly 6:1 at any meaningful volume.

---

## 7. Open Metrics (Not Yet Measured)

The following metrics would be valuable additions to this document but have not been formally measured against the live system:

| Metric | Why Not Yet Measured | How to Measure |
|---|---|---|
| Market Opportunity LLM call success rate (valid JSON shape returned vs. re-raise) | No automated test suite; verification has been live manual testing | Add a logging counter in `analyze_market_opportunity()` — increment on success, on shape-check failure |
| Average opportunity score by industry | No log aggregation; individual scores are visible in browser but not persisted | Add structured logging in `opportunity_score_node` with idea, score, and component subscores |
| Tavily vs. fallback trigger rate | `tools.py` does not log which path was taken | Add a `logger.info("Using Tavily / fallback")` branch in `fetch_results()` |
| Competitor NER hit rate (ideas where ≥1 competitor found vs. zero) | Same as above — not currently logged | Add a log line in `analyze_competitors()` with the count |
| End-to-end request latency distribution | No timing instrumentation | Wrap `pipeline.invoke()` in `main.py` with `time.perf_counter()` before/after and log elapsed time |
| Cache hit rate | Not tracked | Log `"Cache hit"` (already there) and `"Cache miss"` with a counter; expose via `/health` or a separate `/metrics` endpoint |

---

## 8. Document Provenance

All figures in this document are derived directly from the source code as of commit `8334bdb` (September 6, 2026). No figures are estimated or sourced from external benchmarks unless explicitly stated.

| Source | What It Documents |
|---|---|
| [`backend/agent/llm.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/llm.py) | Model names, `reasoning_effort` values, fallback logic, retry cap |
| [`backend/agent/retrieval.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/retrieval.py) | Search angles, per-angle result cap, domain exclusion list |
| [`backend/agent/tools.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/tools.py) | Tavily integration, free fallback chain, relevance scoring formula |
| [`backend/agent/market_agent.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/market_agent.py) | Context window bounds, output validation logic |
| [`backend/agent/competitor_agent.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/competitor_agent.py) | NER filters, mention-count thresholds, price/breadth heuristics |
| [`backend/agent/confidence.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/confidence.py) | Confidence regex patterns, output shape |
| [`backend/agent/opportunity_score.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/opportunity_score.py) | Score weights, signal thresholds, fallback cap |
| [`backend/main.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/main.py) | Cache TTL, cache key normalization, partial-failure response shape |
| [`docs/milestone2-verification.md`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/docs/milestone2-verification.md) | Live test results used in §4.2.2 accuracy table |
| [`AGENTS.md`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/AGENTS.md) | Bug history, design rationale for API-cost trade-offs |
