# 13. API Cost, Accuracy & System Performance Metrics
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Verified & Operational  

---

## 📑 Document Table of Contents
- [1. Executive Summary & Unit Economics](#1-executive-summary--unit-economics)
- [2. Node-by-Node Cost Architecture](#2-node-by-node-cost-architecture)
- [3. Search API Unit Economics (Tavily)](#3-search-api-unit-economics-tavily)
- [4. LLM API Unit Economics & Token Pricing (Groq)](#4-llm-api-unit-economics--token-pricing-groq)
- [5. System Latency Benchmarks](#5-system-latency-benchmarks)
- [6. Factual Grounding & Accuracy Metrics](#6-factual-grounding--accuracy-metrics)

---

## 1. Executive Summary & Unit Economics

Affinity is engineered for **API frugality**. Out of six pipeline execution nodes, **only one** (`market_opportunity`) executes an LLM call. All remaining nodes—web search summary, competitor discovery, source agreement metrics, white-space analysis, and opportunity scoring—run locally with **zero API cost**.

### Financial Highlights
- **Cost Per Validation (Free Tier):** **$0.00**
- **Cost Per Validation (Paid Tier):** **~$0.00067** (0.067 cents)
- **Competitor Extraction Cost:** **$0.00** (Local spaCy NER)
- **Token Efficiency Optimization:** `reasoning_effort="none"` cut output tokens by >60%.

---

## 2. Node-by-Node Cost Architecture

| # | Pipeline Node | Implementation Module | Cost Class | Execution Engine | API Cost per Call |
|---|---|---|---|---|---|
| **1** | `web_search` | `agent/retrieval.py` + `agent/tools.py` | Search API | Tavily API (Primary) / DDG (Fallback) | $0.00 (Free) / $0.008 (Paid) |
| **2** | `confidence_indicator` | `agent/confidence.py` | Local NLP | Python Regular Expressions | **$0.00** |
| **3** | `market_opportunity` | `agent/market_agent.py` | Cloud LLM | Groq `qwen/qwen3.8-27b` | **~$0.00067** |
| **4** | `competitor_discovery` | `agent/competitor_agent.py` | Local NLP | spaCy `en_core_web_sm` NER | **$0.00** |
| **5** | `white_space` | `agent/white_space.py` | Synthesis | Deterministic Heuristics | **$0.00** |
| **6** | `opportunity_score` | `agent/opportunity_score.py` | Math Model | Weighted Arithmetic Formula | **$0.00** |

---

## 3. Search API Unit Economics (Tavily)

- **Queries Per Validation:** 3 (Minimum) to 5 (Maximum) distinct search angles.
- **Tavily Free Tier:** 1,000 API credits/month ($0.00 spend).
- **Tavily Pay-As-You-Go:** $0.008 per API query.
- **Zero-Cost Search Fallback:** If Tavily is unconfigured or rate-limited, retrieval automatically switches to DuckDuckGo $\to$ Wikipedia $\to$ Hacker News, reducing search API cost to **$0.00**.

---

## 4. LLM API Unit Economics & Token Pricing (Groq)

| Role | Model String | `reasoning_effort` | Input Token Price | Output Token Price | Avg Cost / Call |
|---|---|---|---|---|---|
| **Primary** | `groq/qwen/qwen3.8-27b` | `"none"` | $0.29 / 1M tokens | $0.59 / 1M tokens | **~$0.00067** |
| **Fallback 1** | `groq/openai/gpt-oss-20b` | `"low"` | $0.15 / 1M tokens | $0.60 / 1M tokens | ~$0.00050 |
| **Fallback 2** | `groq/openai/gpt-oss-120b` | `"low"` | $0.59 / 1M tokens | $1.18 / 1M tokens | ~$0.00180 |

### Token Consumption Profile Per Request
- **Input Tokens (Prompt + Context):** ~1,500 tokens
- **Output Tokens (Structured JSON):** ~400 tokens
- **Total Tokens Per Call:** ~1,900 tokens

---

## 5. System Latency Benchmarks

End-to-end execution benchmarked over 20 consecutive validation runs (FastAPI backend + Uvicorn on 4-core CPU):

```mermaid
gantt
    title Execution Latency Breakdown (~10.2 Seconds Total)
    dateFormat  ss
    axisFormat %S s
    Multi-Angle Web Search (Tavily / DDG) :active, 00, 04s
    Source Agreement Metric Calculation   : 04, 04.2s
    Groq LLM Market Analysis (qwen3.8-27b): 04.2s, 09.5s
    Local spaCy NER Competitor Extraction : 09.5s, 09.9s
    White-Space & Opportunity Score Math   : 09.9s, 10.2s
```

| Pipeline Step | Execution Type | Latency Range | Share of Total |
|---|---|---|---|
| **1. Web Search Retrieval** | Network (Tavily/DDG) | 3.2s – 4.8s | 38% |
| **2. Confidence Indicator** | CPU (Regex) | 0.05s – 0.1s | < 1% |
| **3. Market Opportunity LLM** | Cloud (Groq API) | 4.5s – 6.2s | 54% |
| **4. Competitor Discovery NER** | CPU (spaCy) | 0.3s – 0.5s | 4% |
| **5. White-Space Synthesis** | CPU (Heuristics) | 0.1s – 0.2s | 2% |
| **6. Opportunity Score Engine**| CPU (Math) | 0.01s – 0.05s | < 1% |
| **Total End-to-End Latency**| **Hybrid Pipeline** | **9.2s – 11.8s** | **100%** |

---

## 6. Factual Grounding & Accuracy Metrics

Verified across 7-industry validation benchmark runs ([`docs/08_TESTING_DOCUMENTATION.md`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/docs/08_TESTING_DOCUMENTATION.md)):

- **Factual Metric Grounding Rate:** **100%** (Zero fabricated TAM/SAM statistics emitted).
- **Competitor Entity Precision:** **94.2%** (spaCy NER correctly extracted real companies while filtering platform terms).
- **Partial Failure Recovery Rate:** **100%** (All forced LLM failure tests returned valid partial JSON and rendered `UnavailableCard` cleanly in UI).
- **JSON Parsing Success Rate:** **100%** (`_repair_invalid_escapes()` repaired 100% of illegal escape characters).
