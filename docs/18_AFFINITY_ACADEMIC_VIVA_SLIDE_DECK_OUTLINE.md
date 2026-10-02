# 18. Academic Viva & Capstone Defense Presentation Guide
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 4.0 · updated 2026-10-02 against the `staging` branch  
**Target Audience:** Capstone Defense Committees, Faculty Evaluators, and Pitch Presenters  
**Companion:** [00_AFFINITY_FINAL_PROJECT_DOCUMENT.md](00_AFFINITY_FINAL_PROJECT_DOCUMENT.md) holds the full detail behind every slide.

> **What changed in 4.0.** Version 3.0 described competitor discovery as spaCy NER with an
> optional refinement pass, a six-tab report, and no tool or comparison slides. The code has
> moved on: competitor discovery now merges local NER with an LLM pass, enriches rivals from
> free public APIs and labels each one direct or indirect; the report has **eight tabs**;
> the pipeline is presented as **18 agents and engines** (9 AI, 9 rule-based); revenue models
> have a rule-based fallback; and the landing page explains the product interactively. This
> version adds slides for the tool stack, the agent map, the comparison with general
> chatbots and the design lessons, and states open items plainly. Numbers marked
> *(re-measure)* come from earlier milestones; refresh them with
> `backend/scripts/latency_token_measurement.py` before presenting.

---

## 📑 Slide Deck Outline
- [Slide 1: Title & Project Overview](#slide-1-title--project-overview)
- [Slide 2: The Venture Validation Dilemma](#slide-2-the-venture-validation-dilemma)
- [Slide 3: Research Questions & Objectives](#slide-3-research-questions--objectives)
- [Slide 4: System Architecture & Pipeline](#slide-4-system-architecture--pipeline)
- [Slide 5: 18 Agents and Engines](#slide-5-18-agents-and-engines)
- [Slide 6: Multi-Angle Search Retrieval & Filtering](#slide-6-multi-angle-search-retrieval--filtering)
- [Slide 7: Market Opportunity Agent & TAM/SAM/SOM](#slide-7-market-opportunity-agent--tamsamsom)
- [Slide 8: Competitor Discovery — NER + LLM + Enrichment](#slide-8-competitor-discovery--ner--llm--enrichment)
- [Slide 9: Direct vs Indirect Rivals & Positioning](#slide-9-direct-vs-indirect-rivals--positioning)
- [Slide 10: Evidence, Confidence & White-Space Gaps](#slide-10-evidence-confidence--white-space-gaps)
- [Slide 11: Opportunity Score, Viability Score & Verdict](#slide-11-opportunity-score-viability-score--verdict)
- [Slide 12: Reliability — Fallback Chain & Fallbacks](#slide-12-reliability--fallback-chain--fallbacks)
- [Slide 13: The Report — Eight Tabs](#slide-13-the-report--eight-tabs)
- [Slide 14: Tools & Services Used](#slide-14-tools--services-used)
- [Slide 15: Why Not Just Ask a Chatbot?](#slide-15-why-not-just-ask-a-chatbot)
- [Slide 16: Accounts, Dashboards & Security](#slide-16-accounts-dashboards--security)
- [Slide 17: Empirical Verification & Bugs Found in Live Testing](#slide-17-empirical-verification--bugs-found-in-live-testing)
- [Slide 18: Cost & Latency](#slide-18-cost--latency)
- [Slide 19: Limitations & Future Work](#slide-19-limitations--future-work)
- [Slide 20: Conclusion & Defense Q&A](#slide-20-conclusion--defense-qa)

---

## Slide 1: Title & Project Overview
- **Title:** Affinity — Development of an AI-Based Startup Idea Validator with Market Analysis Assistance
- **Presenters:** Team Members (Yasaswini, Yalene, Sashi, Anu Kumari, Varshini)
- **Key Message:** A web-grounded validation engine: every market claim is tied to a cited source, and every score is computed by plain code from that evidence.

---

## Slide 2: The Venture Validation Dilemma
- **Problem:** Most early startups fail because there was no real market need.
- **Flaws of Current Options:** Manual desk research takes weeks and costs thousands; a general chatbot answers fluently whether or not anything backs the answer, including market-size figures.
- **Solution:** Multi-angle web retrieval, then specialised agents that must cite their sources, then deterministic scoring on top.

---

## Slide 3: Research Questions & Objectives
- **RQ1:** Can a multi-model fallback chain keep a free-tier LLM pipeline available while preserving factual grounding?
- **RQ2:** Can local spaCy NER plus a single LLM pass discover competitors well enough, while keeping most of the work off the LLM quota?
- **RQ3:** Can confidence be measured from the evidence the analysis actually cites, rather than asserted by the model?
- **Engineering Goals:** Partial-failure isolation (one failed section never blanks the report), cited claims only, reproducible scores.

---

## Slide 4: System Architecture & Pipeline
- **Diagram:** React UI → FastAPI → LangGraph state machine → agents (Groq / Gemini through LiteLLM, local spaCy NER) → Postgres.
- **Pipeline (deep mode, 17 nodes):** web search → confidence indicator → market opportunity → competitor discovery → opportunity score → white space → SWOT → viability score → MVP ∥ GTM (parallel) → contradiction detector → experiments → action plan → assumption tracker → revenue models → confidence dashboard → verdict.
- **Quick mode** runs only market, competitor and white-space analysis.
- **Speaker Notes:** LLMs write the narrative sections. Everything numeric (scores, confidence, verdict) is deterministic Python over that output. Each node is timed and logged, and a failed node is recorded against its own section instead of aborting the run.

---

## Slide 5: 18 Agents and Engines
- **Split:** 9 use a language model; 9 are plain code. Showing the split is the point.
- **AI:** market opportunity, competitor discovery, SWOT and risk, MVP planner, go-to-market, assumption tracker, revenue models, grounding verifier, advisor.
- **Rules:** web research, opportunity score, white-space analyzer, viability index, voice of the market, confidence dashboard, contradiction detector, experiments and action plan, verdict.
- **Naming:** a LangGraph pipeline of single-purpose agents, not an autonomous "swarm". Agents do not negotiate or pick their own tools.
- **Where to see it:** the landing page lists all 18 with the tools behind each.

---

## Slide 6: Multi-Angle Search Retrieval & Filtering
- **Angles:** `Market size & trends`, `Competitors`, `Industry news`, `Customer demand`, `How others solve this`.
- **Blended search:** Tavily and DuckDuckGo results are merged and deduplicated by URL, keeping the best score. A zero-cost fallback chain (Wikipedia, Hacker News) applies only when neither returns.
- **Domain Exclusion:** `_EXCLUDED_DOMAINS` strips `arxiv.org`, and generic directory and review aggregators (for example `competitors.app`, `alternativeto.net`, `saashub.com`, `trustradius.com`) that keyword-match almost any query without being about the idea.

---

## Slide 7: Market Opportunity Agent & TAM/SAM/SOM
- **Engine:** Groq `qwen/qwen3.8-27b` (with fallbacks, see Slide 12).
- **Outputs:** Market-size narrative, structured **TAM / SAM / SOM** tiers (each either a cited claim or `null`), trends and customer segments, all carrying `sourceIds`.
- **Grounding:** A tier with no supporting source is returned as `null` and hidden rather than guessed. A verification pass strips citations whose source doesn't support the claim.

---

## Slide 8: Competitor Discovery — NER + LLM + Enrichment
- **Step 1, local NER:** spaCy `en_core_web_sm` always runs over the snippets at no API cost. A denylist and a product-context test remove generic words mislabelled as companies.
- **Step 2, LLM pass:** reads richer source text and proposes rivals with an offering, a gap, strengths and weaknesses. Merged with the NER list.
- **Step 3, enrichment:** Product Hunt, the iTunes Search API and Wikidata add ratings, pricing and artwork. A name must appear in the matched record's own title, so a lookalike cannot attach the wrong logo.
- **Grounding:** a rival must cite a valid source id. The stricter rule that its name also appear in that source's text was relaxed because it discarded real rivals the model knew from context.
- **History worth telling:** discovery began as an LLM agent, was moved to NER-only to save quota, then returned to an NER-plus-LLM merge once richer output mattered more than the saving.

---

## Slide 9: Direct vs Indirect Rivals & Positioning
- **Mapping:** each rival is labelled **direct** (shares at least two distinct topic stems with the idea, ignoring the target-customer words), **indirect** (shares one), or left unlabelled. Competitor cards group by label.
- **Comparison matrix:** a table of the idea against each rival, with a deterministic fallback.
- **Positioning grid:** Price (`low/mid/high`) × Feature Breadth (`narrow/moderate/broad`). Rivals without price evidence land on `"unknown"` rather than being guessed.
- **Honest limit:** classification can under-label a rival when its source text is thin; a real but off-topic company is a relevance judgement the rule path cannot make.

---

## Slide 10: Evidence, Confidence & White-Space Gaps
- **Headline confidence:** % of the sources the analysis actually **cites** whose relevance score is ≥ 0.5. It used to be computed over the whole raw search pool, which diluted it toward zero; see the [methodology doc](confidence-and-evidence-scoring-methodology.md).
- **Breakdown tiles:** source coverage, cross-source agreement, direct evidence, average relevance, source recency.
- **White Space:** Triangulates customer pain points against competitor density to surface unaddressed gaps.
- **Contradiction detector:** flags claims in one section that conflict with another.

---

## Slide 11: Opportunity Score, Viability Score & Verdict
- **Opportunity Score:** `clamp(marketSizeScore[0-40] + growthScore[0-30] + competitionScore[0-30], 0, 100)` (see doc 15).
- **Market Viability Score:** `0.4·marketDemand + 0.3·(100 − executionRisk) + 0.3·growthVelocity`. Two more axes, **competitionClarity** and **timing**, are reported alongside but left out of the headline because they measure how much is known, not whether the news is good.
- **Verdict:** deterministic *Pursue / Validate first / Rethink* with reasons and one next step.
- **Open item:** the weights are documented but not yet calibrated against a labelled set of ideas.

---

## Slide 12: Reliability — Fallback Chain & Fallbacks
- **Chain:** `groq/qwen/qwen3.8-27b` → `groq/openai/gpt-oss-20b` → `groq/openai/gpt-oss-120b` → `gemini/gemini-3.6-flash` → `gemini/gemini-3.8-flash`.
- **Load split:** competitor discovery starts on `gpt-oss-20b`, go-to-market on `gpt-oss-120b`, the advisor on Gemini, so no single free quota carries the whole run.
- **Switch triggers:** rate limits, missing models, provider errors, **and responses that fail per-attempt shape validation** (e.g. unparseable JSON).
- **Provider limits that shaped it:** Qwen has a hard 1,000 output-token/minute cap, so its calls stay under about 950 tokens; `gpt-oss` models have 8,000 tokens/minute and a daily cap; Gemini's free tier allows about 20 requests/day/model.
- **Last resort:** a local Ollama model (only where one runs), then one cloud retry after a cooldown, then a labelled deterministic fallback. The "enter your email" prompt appears only where a local model exists.
- **Revenue models:** if the model call fails, the section is built from how found competitors describe their pricing, labelled as inferred. Previously it came back empty.

---

## Slide 13: The Report — Eight Tabs
- **Tabs:** Evidence, Market, Competitors, Customers, Gaps, Risks, Build & Ship, Roadmap.
- **Why eight:** the earlier six-tab layout grouped "Market & Rivals" and "Gaps & Exposure", which made two tabs very long. Splitting them lets each tab answer one question.
- **Around it:** verdict card, confidence dashboard, contradiction banner, advisor chat that jumps to the section it used, PDF export, email delivery.
- **Landing page:** interactive "How it works" with the tools behind each step, the 18-agent grid, a tool-stack section, and the chatbot comparison. The hero takes an idea directly and the form offers sample ideas.

---

## Slide 14: Tools & Services Used
- **Orchestration and agents:** LangGraph, CrewAI (one single-task agent per AI section), LiteLLM (one interface to Groq and Gemini).
- **Evidence:** Tavily, DuckDuckGo, spaCy, Product Hunt, iTunes Search, Wikidata.
- **Delivery:** **ReportLab** builds the PDF on the server; **SendGrid's HTTP API** emails the report (chosen because the host blocks SMTP ports); FastAPI serves it all.
- **Accounts and storage:** PostgreSQL on Neon (SQLite locally) through SQLAlchemy, bcrypt and JWT, optional Google sign-in.
- **Frontend:** React 19, Vite, Tailwind 4, tested with Vitest. Hosted on Render.

---

## Slide 15: Why Not Just Ask a Chatbot?
- **Fair framing:** assistants such as ChatGPT and Claude reason well and can browse. The difference is how checkable the answer is.
- **Evidence:** fixed five-angle search with every source listed, versus training data unless asked to search.
- **Claims:** each tagged Grounded or Inferred and verified, versus fluent text whether or not anything backs it.
- **Scoring:** computed by code and repeatable for the same evidence, versus whatever the model says that time.
- **Output and memory:** tabs, PDF, emailed copy, saved history and comparison, versus a chat reply per conversation.
- **Caution when presenting:** compare behaviours we can show; avoid claims about other products we have not tested.

---

## Slide 16: Accounts, Dashboards & Security
- **Accounts:** optional email + password (bcrypt, 30-day JWT) and Google sign-in. Anonymous validation still works.
- **Account menu:** History, Compare ideas, Dashboard, and (admins only) Platform health.
- **Founder Dashboard:** Overview, Comparison matrix, Validation history, Score trends.
- **Admin Platform Health:** validations/day, cache hit rate, API success rate, deep-analysis rate, latency by node, model usage, recent errors, email delivery, backed by a durable `events` log. Admin access comes only from the `ADMIN_EMAILS` environment variable.
- **Retention:** sessions 7 days, cache 30 minutes, events 90 days; per-IP rate limits on auth, validate, chat, export and email.
- **Share links:** a report's session id is a random UUID that works as a link, so report, chat and PDF endpoints need no sign-in; anyone holding the link can open that report.

---

## Slide 17: Empirical Verification & Bugs Found in Live Testing
- **Tested domains:** Student Budgeting, Coffee Subscriptions, Meal Prep, Photo Invoicing, Fintech, Health Journaling, Smart Water Bottle.
- **Method lesson:** live search varies run to run, so one good or bad run proves little; fixes were checked across several ideas.
- **Defects found only by live testing:** fallback chain stopping early, confidence diluted by the raw search pool, TAM/SAM/SOM computed but not shown, admin access lost on redeploy, junk competitor names, a positioning grid that never rendered, and revenue models silently empty when quota ran out. Each has a regression test.
- **Partial failure:** a failed section returns an inline error card; the rest of the report still renders.
- **Suites:** about 520 backend and about 100 frontend tests; two backend tests are environment-dependent and fail when real keys are present.
- Details: [milestone2-verification.md](milestone2-verification.md), [milestone4-verification.md](milestone4-verification.md).

---

## Slide 18: Cost & Latency
- **Free-tier operation:** Groq + Gemini free tiers, free search and enrichment APIs, Render free tier.
- **Latency:** the original single-LLM pipeline measured ~10 s *(re-measure: deep mode now runs many more LLM-backed steps; quick mode is the fast path)*.
- **Per-request cost:** ~$0.00067 on paid tiers at Milestone 2 *(re-measure)*.
- **Real constraint:** quota, not money. Heavy testing exhausts the free per-minute and daily limits, which is why the fallbacks above exist.

---

## Slide 19: Limitations & Future Work
- **Not built yet:** charts in the PDF export; a calibration of the score weights against labelled ideas; a measured competitor-recall figure; a written scaling plan beyond free tiers; progressive rendering of sections as they finish; a saved real example report on the landing page.
- **Operational:** sessions expire after 7 days; Render's free Postgres expires after 30 days; a free host sleeps when idle and the free database auto-suspends, which slows the first sign-in; no password reset or email verification yet.
- **Technical:** the local-model fallback needs real GPU hardware; rival classification under-labels on thin text.
- Full list: [known-limitations-and-future-work.md](known-limitations-and-future-work.md), [scaling-options.md](scaling-options.md).

---

## Slide 20: Conclusion & Defense Q&A
- **Summary:** A working multi-agent startup validator combining live web retrieval, local NER plus LLM competitor discovery, cited analysis and deterministic scoring, with accounts, dashboards, PDF and email delivery.
- **Likely questions to prepare:** How is confidence computed and why trust it? What happens when every LLM is rate-limited? Why did competitor discovery move from NER-only back to NER plus LLM? What is the difference between your pipeline and a "swarm"? What is not done yet? How is admin access controlled? What data is kept and for how long?
