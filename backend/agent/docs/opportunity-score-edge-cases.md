# Opportunity Score Edge Case Testing

## Purpose

This document covers edge-case testing for the Milestone 2 Opportunity Score calculation.

The score is calculated from:

- Market size signal: up to 40 points
- Market growth/trend signal: up to 30 points
- Competitor density: up to 30 points

When both upstream agents fail to produce grounded data, the system can fall back to raw web search results with a maximum fallback score of 50.

---

## Edge Cases to Test

| Test Case | Input Condition | Expected Result | Actual Result | Status |
|---|---|---|---|---|
| No sources | Empty market data, competitors, and search results | Score = 0 and no crash | Pending | Pending |
| No LLM output but search results exist | Empty market and competitor data with valid search results | Grounded fallback score, maximum 50 | Pending | Pending |
| None inputs | `market_data=None`, `competitor_data=None`, `search_results=None` | Score = 0 and no crash | Pending | Pending |
| Valid market, no competitors | Market data exists but competitor list is empty | Normal score calculation; competition can contribute 30 points | Pending | Pending |
| Market size only | Valid `marketSize`, but empty trends, segments, and competitors | Market size should contribute to the score and should not be treated as completely ungrounded data | Pending | Pending |
| Strong market signal | Market size contains signals such as `billion`, `large`, `global`, or `high growth` | Market size score = 40 | Pending | Pending |
| Medium market signal | Market size contains `million`, `growing`, `regional`, or `expanding` | Market size score = 25 | Pending | Pending |
| Weak market signal | Non-empty market size without strong or medium signals | Market size score = 15 | Pending | Pending |
| Insufficient market data | Market size contains `not enough grounded data` | Market size score = 0 | Pending | Pending |
| No trends | Empty trends list | Growth score = 0 | Pending | Pending |
| One positive trend | One trend containing growth/adoption/demand signal | Growth score = 12 | Pending | Pending |
| Two positive trends | Two trends containing positive growth signals | Growth score = 22 | Pending | Pending |
| Three or more positive trends | Three or more positive growth signals | Growth score = 30 | Pending | Pending |
| Trends without positive signals | Trends exist but contain no positive growth signal | Growth score = 6 | Pending | Pending |
| Zero competitors with grounded market data | Valid market data and `competitors=[]` | Competition score = 30 | Pending | Pending |
| One competitor | One competitor identified | Competition score = 24 | Pending | Pending |
| Two competitors | Two competitors identified | Competition score = 18 | Pending | Pending |
| Three competitors | Three competitors identified | Competition score = 12 | Pending | Pending |
| Four or more competitors | Four or more competitors identified | Competition score = 6 | Pending | Pending |
| Score bounds | Any combination of valid or partial data | Final score always remains between 0 and 100 | Pending | Pending |
| Search fallback cap | Large number of high-relevance search results but no LLM agent data | Fallback score must not exceed 50 | Pending | Pending |
| Partial agent failure | Market agent returns data but competitor agent fails, or vice versa | Pipeline should not crash and score should use available grounded data safely | Pending | Pending |
