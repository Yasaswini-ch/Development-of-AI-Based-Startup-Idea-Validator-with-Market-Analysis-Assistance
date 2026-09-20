# 15. Opportunity Score Formula

**Document Version:** 3.0 (corrected — see note below)
**Status:** Verified & Operational

---

> **Correction from earlier drafts of this document:** a previous version described a
> `Base=50 + market + growth − density + gaps` formula with a "White-Space Gap
> Component," specific weight tables (+15/+10/+5, CAGR thresholds, a
> "Blue Ocean"/"High Saturation" competitor-count scale), and a code listing that
> doesn't match the real module at all. None of that formula or code exists.
> `backend/agent/opportunity_score.py` has no `Base=50`, no subtraction term, and no
> white-space component whatsoever. This version documents the real, additive-only
> formula.

## 1. Executive Summary

The **Opportunity Score** is a **0–100 integer**, computed deterministically in
`backend/agent/opportunity_score.py` — no LLM call, no `Base` constant, no subtraction.
It's a straight sum of three independent components, each already individually capped,
then clamped to `[0, 100]` (the clamp is a safety net; the components can't actually
exceed 100 on their own since they sum to at most 100).

## 2. The Real Formula

```
OpportunityScore = clamp(marketSizeScore + growthScore + competitionScore, 0, 100)
```

Three components, weighted **40 / 30 / 30**:

### 2.1 Market Size Score (max 40)

Keyword-matched against `marketOpportunity.marketSize` (case-insensitive substring
match, not a regex, not a parsed dollar figure):

| Signal found | Score |
|---|---|
| "billion", "large", "global", "rapidly growing", "high growth" | **40** |
| "million", "growing", "regional", "expanding" | 25 |
| any non-empty text not containing "not enough" | 15 |
| empty / no market size text | 0 |

### 2.2 Growth Score (max 30)

Counts how many entries in `marketOpportunity.trends[]` contain a positive-growth
keyword ("growth", "growing", "increase", "rising", "demand", "adoption", "expanding",
"surge"):

| Positive-signal trend count | Score |
|---|---|
| ≥ 3 | **30** |
| 2 | 22 |
| 1 | 12 |
| 0 (but trends list is non-empty) | 6 |
| trends list is empty | 0 |

### 2.3 Competition Score (max 30)

Purely a function of `len(competitors.competitors)` — fewer named competitors scores
higher:

| Competitor count | Score |
|---|---|
| 0 | **30** |
| 1 | 24 |
| 2 | 18 |
| 3 | 12 |
| 4+ | 6 |

There is no CAGR parsing, no dollar-amount parsing, and no white-space component in
this score at all — `agent/white_space.py`'s output is never read by
`opportunity_score.py`.

## 3. Fallback Behavior (real, not the table from the earlier draft)

If **both** `marketOpportunity` and `competitors` come back with no trends, no
segments, and no competitors at all (`_has_no_grounded_data()` — almost certainly a
Groq rate limit or rejected LLM output, not a genuinely empty market), the function
does **not** run the three components above at all — an empty competitor list would
otherwise score a misleadingly perfect 30/30 ("no competition!") on a run that produced
no real data. Instead it falls back to `_search_fallback_score()`, computed from the
raw web search results (which don't depend on the LLM at all):

```
countScore      = min(len(search_results), 10) / 10 * 25
relevanceScore  = average(result.score for result in search_results) * 25
fallbackScore   = round(min(50, countScore + relevanceScore))
```

capped at **50**, not the full 0–100 range — a weaker, unanalyzed signal is
deliberately never allowed to look as confident as a real agent analysis. Only
returns `0` outright when there are no search results at all to fall back to.

## 4. Real Code (verbatim, `backend/agent/opportunity_score.py`)

```python
_MARKET_SIZE_WEIGHT = 40
_GROWTH_WEIGHT = 30
_COMPETITION_WEIGHT = 30
_SEARCH_FALLBACK_CAP = 50

def calculate_opportunity_score(market_data, competitor_data, search_results=None) -> int:
    market_data = market_data or {}
    competitor_data = competitor_data or {}

    if _has_no_grounded_data(market_data, competitor_data):
        return _search_fallback_score(search_results or [])

    market_score = _market_size_score(market_data.get("marketSize", ""))
    growth_score = _growth_score(market_data.get("trends", []))
    competition_score = _competition_score(competitor_data.get("competitors", []))

    total = market_score + growth_score + competition_score
    return max(0, min(100, total))
```
