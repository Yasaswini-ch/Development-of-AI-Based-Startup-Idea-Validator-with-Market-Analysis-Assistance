# 18. Academic Viva & Capstone Defense Presentation Guide
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 3.0 · updated 2026-09-26 against the `staging` branch  
**Target Audience:** Capstone Defense Committees, Faculty Evaluators, and Pitch Presenters  

> **What changed in 3.0.** Version 2.0 said the app had "no user accounts, no
> authentication", listed the comparison matrix and admin dashboards as future work,
> and described a single-LLM pipeline. All of that is out of date. This version matches
> the current code: optional JWT accounts with an admin role, a founder Dashboard with
> a comparison matrix, an admin Platform Health view, a multi-agent pipeline with a
> validated LLM fallback chain, and cited-source confidence scoring. Numbers marked
> *(re-measure)* come from earlier milestones; refresh them with
> `backend/scripts/latency_token_measurement.py` before presenting.

---

## 📑 Slide Deck Outline
- [Slide 1: Title & Project Overview](#slide-1-title--project-overview)
- [Slide 2: The Venture Validation Dilemma](#slide-2-the-venture-validation-dilemma)
- [Slide 3: Research Questions & Objectives](#slide-3-research-questions--objectives)
- [Slide 4: System Architecture & Multi-Agent Pipeline](#slide-4-system-architecture--multi-agent-pipeline)
- [Slide 5: Multi-Angle Search Retrieval & Filtering](#slide-5-multi-angle-search-retrieval--filtering)
- [Slide 6: Market Opportunity Agent & TAM/SAM/SOM](#slide-6-market-opportunity-agent--tamsamsom)
- [Slide 7: Competitor Discovery (spaCy NER + refinement)](#slide-7-competitor-discovery-spacy-ner--refinement)
- [Slide 8: 3x3 Competitor Positioning Grid](#slide-8-3x3-competitor-positioning-grid)
- [Slide 9: Evidence, Confidence & White-Space Gaps](#slide-9-evidence-confidence--white-space-gaps)
- [Slide 10: Opportunity Score, Viability Score & Verdict](#slide-10-opportunity-score-viability-score--verdict)
- [Slide 11: Reliability — LLM Fallback Chain](#slide-11-reliability--llm-fallback-chain)
- [Slide 12: Accounts, Dashboards & Comparison Matrix](#slide-12-accounts-dashboards--comparison-matrix)
- [Slide 13: Security, Privacy & Data Retention](#slide-13-security-privacy--data-retention)
- [Slide 14: Empirical Verification & Bugs Found in Live Testing](#slide-14-empirical-verification--bugs-found-in-live-testing)
- [Slide 15: Cost & Latency](#slide-15-cost--latency)
- [Slide 16: Limitations & Future Work](#slide-16-limitations--future-work)
- [Slide 17: Conclusion & Defense Q&A](#slide-17-conclusion--defense-qa)

---

## Slide 1: Title & Project Overview
- **Title:** Affinity — Development of an AI-Based Startup Idea Validator with Market Analysis Assistance
- **Presenters:** Team Members (Yasaswini, Yalene, Sashi, Anu Kumari, Varshini)
- **Key Message:** A web-grounded validation engine: every market claim is tied to a cited source, and every score is computed deterministically from that evidence.

---

## Slide 2: The Venture Validation Dilemma
- **Problem:** 42% of startups fail due to lack of market need.
- **Flaws of Current Options:** Manual desk research takes weeks and costs $5,000+; naive chatbot prompts emit unsourced TAM/SAM figures.
- **Solution:** Multi-angle web retrieval + specialised agents that must cite their sources + deterministic scoring on top.

---

## Slide 3: Research Questions & Objectives
- **RQ1:** Can a multi-model fallback chain keep a free-tier LLM pipeline available while preserving factual grounding?
- **RQ2:** Can local spaCy NER discover competitors without spending LLM quota?
- **RQ3:** Can confidence be measured from the evidence the analysis actually cites, rather than asserted by the model?
- **Engineering Goals:** Partial-failure isolation (one failed section never blanks the report), cited claims only, reproducible scores.

---

## Slide 4: System Architecture & Multi-Agent Pipeline
- **Diagram:** React UI → FastAPI → LangGraph state machine → agents (Groq / Gemini LLMs, local spaCy NER) → Postgres.
- **Pipeline (deep mode):** web search → confidence indicator → market opportunity → competitor discovery → opportunity score → white space → SWOT → viability score → MVP ∥ GTM (parallel) → contradiction detector → experiments → action plan → assumption tracker → revenue models → confidence dashboard → verdict.
- **Quick mode** runs only market, competitor and white-space analysis.
- **Speaker Notes:** LLMs write the narrative sections (market, SWOT, MVP, GTM, assumptions, revenue models, claim verification). Everything numeric (scores, confidence, verdict) is deterministic Python over that output.

---

## Slide 5: Multi-Angle Search Retrieval & Filtering
- **Angles:** `Market size & trends`, `Competitors`, `Industry news`, `Customer demand`, `How others solve this`.
- **Zero-Cost Fallback:** Tavily API → DuckDuckGo → Wikipedia → Hacker News.
- **Domain Exclusion:** `_EXCLUDED_DOMAINS` strips `arxiv.org` and directory aggregators.

---

## Slide 6: Market Opportunity Agent & TAM/SAM/SOM
- **Engine:** Groq `qwen/qwen3.8-27b` (with fallbacks, see Slide 11).
- **Outputs:** Market-size narrative, structured **TAM / SAM / SOM** tiers (each either a cited claim or `null`), trends and customer segments, all carrying `sourceIds`.
- **Grounding:** A tier with no supporting source is returned as `null` and hidden in the UI rather than guessed. A verification pass strips citations whose source doesn't support the claim.

---

## Slide 7: Competitor Discovery (spaCy NER + refinement)
- **Engine:** Local spaCy `en_core_web_sm` parses search snippets; an optional Gemini pass refines price tier and feature breadth.
- **Precision Rules:** Generic word denylist, single-word product context validation (`_has_product_context`), camelCase preservation.
- **Economics:** Discovery itself costs no LLM quota.

---

## Slide 8: 3x3 Competitor Positioning Grid
- **Matrix:** Price (`low/mid/high`) × Feature Breadth (`narrow/moderate/broad`).
- **Unplaced Competitors:** Items lacking price evidence land on `"unknown"` rather than being guessed.

---

## Slide 9: Evidence, Confidence & White-Space Gaps
- **Headline confidence:** % of the sources the analysis actually **cites** whose relevance score is ≥ 0.5. It used to be computed over the whole raw search pool, which diluted it toward zero; see the [methodology doc](confidence-and-evidence-scoring-methodology.md).
- **Breakdown tiles:** source coverage, cross-source agreement, direct evidence, average relevance, source recency.
- **White Space:** Triangulates customer pain points against competitor density to surface unaddressed gaps.
- **Contradiction detector:** flags claims in one section that conflict with another.

---

## Slide 10: Opportunity Score, Viability Score & Verdict
- **Opportunity Score:** `clamp(marketSizeScore[0-40] + growthScore[0-30] + competitionScore[0-30], 0, 100)` (see doc 15).
- **Market Viability Score:** `0.4·marketDemand + 0.3·(100 − executionRisk) + 0.3·growthVelocity`. Two more axes, **competitionClarity** and **timing**, are reported alongside but deliberately left out of the headline because they measure how much is known, not whether the news is good.
- **Verdict:** deterministic *Pursue / Validate first / Rethink* with reasons and one next step.

---

## Slide 11: Reliability — LLM Fallback Chain
- **Chain:** `groq/qwen/qwen3.8-27b` → `groq/openai/gpt-oss-20b` → `groq/openai/gpt-oss-120b` → `gemini/gemini-3.6-flash` → `gemini/gemini-3.8-flash`.
- **Switch triggers:** rate limits, missing models, provider/network errors, **and responses that fail per-attempt shape validation** (e.g. unparseable JSON).
- **Last resort:** if every cloud model fails, a local Ollama model is tried (only where one is actually running), then the whole cloud chain is retried once after a short cooldown. If that fails too, the section shows a clearly labelled deterministic fallback. The "enter your email for deeper analysis" prompt only appears where a local model exists.

---

## Slide 12: Accounts, Dashboards & Comparison Matrix
- **Accounts:** optional email + password sign-in (bcrypt, 30-day JWT). Anonymous validation still works.
- **Account menu:** one dropdown with History, Compare ideas, Dashboard, and (admins only) Platform health.
- **Founder Dashboard:** four tabs: Overview, Comparison matrix, Validation history, Score trends.
- **Admin Platform Health:** validations/day, cache hit rate, API success rate, deep-analysis rate, latency by node, model usage, top categories, recent errors, email delivery. Backed by a durable `events` log.
- **Admin access:** granted through the `ADMIN_EMAILS` environment variable; there is no self-service route.

---

## Slide 13: Security, Privacy & Data Retention
- **Storage:** Postgres in production (SQLite locally). Validation sessions expire after 7 days (200-row cap), cache after 30 minutes, events after 90 days. Accounts persist.
- **Auth:** bcrypt passwords, HS256 JWT, per-IP rate limits on auth, validate, chat, export and email.
- **Session links:** a report's session id is a random UUID that works as a share link, so report, chat and PDF endpoints don't require sign-in.
- **Client:** the in-progress result lives in `sessionStorage` (cleared on tab close); the auth token and device history live in `localStorage`.

---

## Slide 14: Empirical Verification & Bugs Found in Live Testing
- **Tested Domains:** Student Budgeting, Coffee Subscriptions, Meal Prep, Photo Invoicing, Fintech, Health Journaling, Smart Water Bottle.
- **Partial failure:** a failed section returns an inline error card; the rest of the report still renders.
- **Live-testing fixes (Sept 2026):** fallback chain stopping after 2 of 5 models, confidence diluted by the raw search pool, TAM/SAM/SOM computed but not shown, admin access lost on redeploy. Each has a regression test; see [milestone4-verification.md](milestone4-verification.md).

---

## Slide 15: Cost & Latency
- **Free-tier operation:** Groq + Gemini free tiers, free search fallbacks, Render free tier.
- **Latency:** Milestone 2 measured ~10 s for the original single-LLM pipeline *(re-measure: deep mode now runs many more LLM-backed steps; quick mode is the fast path)*.
- **Per-request cost:** ~$0.00067 on paid tiers at Milestone 2 *(re-measure)*.

---

## Slide 16: Limitations & Future Work
- Validation sessions expire after 7 days even for signed-in users.
- Render's free Postgres expires 30 days after creation.
- No password reset or email verification yet.
- The local-model fallback needs real GPU hardware to be practical.
- Two overlapping documentation sets (numbered vs. lowercase) — a process lesson.
- Full list: [known-limitations-and-future-work.md](known-limitations-and-future-work.md).

---

## Slide 17: Conclusion & Defense Q&A
- **Summary:** A working multi-agent startup validator combining live web retrieval, local NER, cited LLM analysis and deterministic scoring, with accounts, dashboards and an admin view.
- **Likely questions to prepare:** How is confidence computed and why trust it? What happens when every LLM is rate-limited? How is admin access controlled? What data is kept and for how long?
