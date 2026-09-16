# 18. Academic Viva & Capstone Defense Presentation Guide
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Target Audience:** Capstone Defense Committees, Faculty Evaluators, and Pitch Presenters  

---

## 📑 Slide Deck Outline
- [Slide 1: Title & Project Overview](#slide-1-title--project-overview)
- [Slide 2: The Venture Validation Dilemma](#slide-2-the-venture-validation-dilemma)
- [Slide 3: Research Questions & Objectives](#slide-3-research-questions--objectives)
- [Slide 4: System Architecture & Hybrid Agent Model](#slide-4-system-architecture--hybrid-agent-model)
- [Slide 5: Multi-Angle Search Retrieval & Filtering](#slide-5-multi-angle-search-retrieval--filtering)
- [Slide 6: Market Opportunity LLM Agent](#slide-6-market-opportunity-llm-agent)
- [Slide 7: Local spaCy NER Competitor Discovery](#slide-7-local-spacy-ner-competitor-discovery)
- [Slide 8: 3x3 Competitor Positioning Grid](#slide-8-3x3-competitor-positioning-grid)
- [Slide 9: Cross-Source Consensus & White-Space Gaps](#slide-9-cross-source-consensus--white-space-gaps)
- [Slide 10: Opportunity Score Mathematical Model](#slide-10-opportunity-score-mathematical-model)
- [Slide 11: Information Security & Data Privacy](#slide-11-information-security--data-privacy)
- [Slide 12: Empirical Verification (7 Domains)](#slide-12-empirical-verification-7-domains)
- [Slide 13: Financial Economics & API Benchmarks](#slide-13-financial-economics--api-benchmarks)
- [Slide 14: Limitations & Future Roadmap](#slide-14-limitations--future-roadmap)
- [Slide 15: Conclusion & Defense Q&A](#slide-15-conclusion--defense-qa)

---

## Slide 1: Title & Project Overview
- **Title:** Affinity — Development of an AI-Based Startup Idea Validator with Market Analysis Assistance
- **Presenters:** Team Members (Yasaswini, Yalene, Sashi, Anu Kumari, Varshini)
- **Key Message:** An automated, web-grounded validation engine that evaluates startup feasibility in ~10 seconds.

---

## Slide 2: The Venture Validation Dilemma
- **Problem:** 42% of startups fail due to lack of market need.
- **Flaws of Current Options:** Manual desk research takes weeks and costs $5,000+; naive ChatGPT prompts emit hallucinated TAM/SAM metrics.
- **Solution:** Multi-angle web retrieval + local spaCy NER + Groq LLM market reasoning.

---

## Slide 3: Research Questions & Objectives
- **RQ1:** Can hybrid agent scoping eliminate LLM rate limits while preserving factual grounding?
- **RQ2:** Can local spaCy NER extract competitors at $0.00 API token cost?
- **Engineering Goals:** Latency < 15s, LLM calls $\le 1$ per request, 100% partial-failure isolation.

---

## Slide 4: System Architecture & Hybrid Agent Model
- **Diagram:** Multi-tier topology (React UI $\to$ FastAPI Gateway $\to$ LangGraph State Machine $\to$ Groq / Local spaCy NER).
- **Speaker Notes:** Explain why only Market Opportunity uses an LLM while Competitor Discovery runs locally via spaCy NER.

---

## Slide 5: Multi-Angle Search Retrieval & Filtering
- **Angles:** `Market size & trends`, `Competitors`, `Industry news`, `Customer demand`, `How others solve this`.
- **Zero-Cost Fallback:** Tavily API $\to$ DuckDuckGo $\to$ Wikipedia $\to$ Hacker News.
- **Domain Exclusion:** `_EXCLUDED_DOMAINS` strips `arxiv.org` and directory aggregators.

---

## Slide 6: Market Opportunity LLM Agent
- **Engine:** Groq `qwen/qwen3.8-27b` with `reasoning_effort="none"`.
- **Outputs:** Market size, CAGR, trends, 4 customer segment profiles (pain points, motivations, buying behaviors).
- **Grounding:** Strict negative prompts force *"TAM/SAM not clear"* when figures are absent in search text.

---

## 7. Local spaCy NER Competitor Discovery
- **Engine:** Local spaCy `en_core_web_sm` parsing search snippets.
- **Precision Rules:** Generic word denylist, single-word product context validation (`_has_product_context`), camelCase preservation.
- **Economics:** $0.00 API cost, zero rate limit.

---

## Slide 8: 3x3 Competitor Positioning Grid
- **Matrix:** Price (`low/mid/high`) $\times$ Feature Breadth (`narrow/moderate/broad`).
- **Heuristics:** Extracted from local 2-sentence competitor text snippet.
- **Unplaced Competitors:** Items lacking price evidence land on `"unknown"`.

---

## Slide 9: Cross-Source Consensus & White-Space Gaps
- **Consensus:** Regex-based source agreement counts (*"4/5 agree market is growing"*).
- **White Space:** Triangulates customer pain points against competitor density to surface unaddressed feature gaps.

---

## Slide 10: Opportunity Score Mathematical Model
- **Formula:** $\text{Score} = \text{Clamp}(50 + S_{\text{market}} + S_{\text{growth}} - S_{\text{density}} + S_{\text{gaps}}, 0, 100)$
- **Determinism:** Non-LLM mathematical formula ensures stable, reproducible scoring.

---

## Slide 11: Information Security & Data Privacy
- **Stateless:** Zero persistent database storage.
- **Caching:** Volatile in-memory cache (30-min TTL) keyed by SHA-256 hash.
- **Client:** Browser `sessionStorage` purges data on tab close.

---

## Slide 12: Empirical Verification (7 Domains)
- **Tested Domains:** Student Budgeting, Coffee Subscriptions, Meal Prep, Photo Invoicing, Fintech, Health Journaling, Smart Water Bottle.
- **Forced Failure Check:** Proved API returns `200 OK` partial JSON with inline error cards when LLM fails.

---

## Slide 13: Financial Economics & API Benchmarks
- **Paid Tier Cost:** ~$0.00067 per validation request.
- **Free Tier Cost:** $0.00.
- **Latency:** ~10.2 seconds total processing time.

---

## Slide 14: Limitations & Future Roadmap
- **Limitations:** Off-topic company relevance in search snippets; rough pricing heuristic bounds.
- **Roadmap:** Milestone 3 (PDF export, comparison matrix); Milestone 4 (Authenticated user workspaces, webhooks).

---

## Slide 15: Conclusion & Defense Q&A
- **Summary:** Delivered a operational hybrid startup validator combining live web retrieval, local NER, and single-LLM market synthesis.
- **Defense Readiness:** Prepared responses for faculty questions regarding accuracy, cost, privacy, and LLM rate limits.
