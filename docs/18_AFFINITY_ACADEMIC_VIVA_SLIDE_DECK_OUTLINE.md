# 18. Academic Viva & Capstone Defense Presentation Guide
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 5.0 · updated 2026-10-02 against the `staging` branch  
**Target Audience:** Capstone Defense Committees, Faculty Evaluators, and Pitch Presenters  
**Companion:** [00_AFFINITY_FINAL_PROJECT_DOCUMENT.md](00_AFFINITY_FINAL_PROJECT_DOCUMENT.md) holds the full detail behind every slide.

> **What changed in 5.0.** Version 4.0 was accurate but ordered by topic. This version
> follows the **layout of the product itself**: the landing page and input, then each tab of
> the report in the order a founder sees it, then the advisor and delivery, then the
> platform around it (accounts, reliability, tools), then evidence of testing and limits.
> Every slide was re-checked against the code. Corrections made in this pass: competitor
> discovery is now described as **multi-source** (web search, local NER, an LLM pass and
> three public APIs); SAM and SOM can now appear as **labelled estimates** when no source
> states them; quick mode is described as skipping the strategy nodes; the email links to the
> report rather than attaching the PDF. Numbers marked *(re-measure)* come from earlier
> milestones; refresh them with `backend/scripts/latency_token_measurement.py` before presenting.

---

## 📑 Slide Deck Outline

**Part A: Context**
- [Slide 1: Title & Project Overview](#slide-1-title--project-overview)
- [Slide 2: The Venture Validation Dilemma](#slide-2-the-venture-validation-dilemma)
- [Slide 3: Research Questions & Objectives](#slide-3-research-questions--objectives)

**Part B: How it is built**
- [Slide 4: System Architecture & Pipeline](#slide-4-system-architecture--pipeline)
- [Slide 5: 18 Agents and Engines](#slide-5-18-agents-and-engines)

**Part C: The product, in the order a founder sees it**
- [Slide 6: Landing Page, Input & the Report at a Glance](#slide-6-landing-page-input--the-report-at-a-glance)
- [Slide 7: Evidence Tab — Search Retrieval & Filtering](#slide-7-evidence-tab--search-retrieval--filtering)
- [Slide 8: Competitors Tab — Discovery from Multiple Sources](#slide-8-competitors-tab--discovery-from-multiple-sources)
- [Slide 9: Competitors Tab — Direct vs Indirect, Matrix & Positioning](#slide-9-competitors-tab--direct-vs-indirect-matrix--positioning)
- [Slide 10: Market Tab — Sizing, Trends & Viability](#slide-10-market-tab--sizing-trends--viability)
- [Slide 11: Customers Tab — Segments & Voice of the Market](#slide-11-customers-tab--segments--voice-of-the-market)
- [Slide 12: Gaps Tab — White Space & Entry Wedge](#slide-12-gaps-tab--white-space--entry-wedge)
- [Slide 13: Risks Tab — SWOT, Bear Case, Assumptions & Contradictions](#slide-13-risks-tab--swot-bear-case-assumptions--contradictions)
- [Slide 14: Build & Ship Tab — MVP, Revenue Models & Go-to-Market](#slide-14-build--ship-tab--mvp-revenue-models--go-to-market)
- [Slide 15: Roadmap Tab — Timeline, Experiments & Action Plan](#slide-15-roadmap-tab--timeline-experiments--action-plan)
- [Slide 16: Trusting the Result — Grounded vs Inferred & Confidence](#slide-16-trusting-the-result--grounded-vs-inferred--confidence)
- [Slide 17: Scores & the Verdict](#slide-17-scores--the-verdict)
- [Slide 18: The Advisor Chat](#slide-18-the-advisor-chat)
- [Slide 19: Delivery — PDF & Email](#slide-19-delivery--pdf--email)

**Part D: The platform around it**
- [Slide 20: Accounts, Dashboards & Security](#slide-20-accounts-dashboards--security)
- [Slide 21: Reliability — Fallback Chain & Fallbacks](#slide-21-reliability--fallback-chain--fallbacks)
- [Slide 22: Tools & Services Used](#slide-22-tools--services-used)
- [Slide 23: Why Not Just Ask a Chatbot?](#slide-23-why-not-just-ask-a-chatbot)

**Part E: Evidence and honesty**
- [Slide 24: Verification, Bugs Found & User Test](#slide-24-verification-bugs-found--user-test)
- [Slide 25: Cost & Latency](#slide-25-cost--latency)
- [Slide 26: Limitations & Future Work](#slide-26-limitations--future-work)
- [Slide 27: Conclusion & Defense Q&A](#slide-27-conclusion--defense-qa)

---

# Part A: Context

## Slide 1: Title & Project Overview
- **Title:** Affinity — Development of an AI-Based Startup Idea Validator with Market Analysis Assistance
- **Presenters:** Team Members (Yasaswini, Yalene, Sashi, Anu Kumari, Varshini)
- **Key Message:** A web-grounded validation engine: every market claim is tied to a cited source, and every score is computed by plain code from that evidence.

---

## Slide 2: The Venture Validation Dilemma
- **Problem:** Most early startups fail because there was no real market need.
- **Flaws of current options:** manual desk research takes weeks and costs thousands; a general chatbot answers fluently whether or not anything backs the answer, including market-size figures.
- **Solution:** multi-angle web retrieval, then specialised agents that must cite their sources, then deterministic scoring on top.

---

## Slide 3: Research Questions & Objectives
- **RQ1:** Can a multi-model fallback chain keep a free-tier LLM pipeline available while preserving factual grounding?
- **RQ2:** Can competitors be discovered reliably by combining several cheap sources (local NER, public APIs) with one LLM pass, rather than relying on an LLM alone?
- **RQ3:** Can confidence be measured from the evidence the analysis actually cites, rather than asserted by the model?
- **Engineering goals:** partial-failure isolation (one failed section never blanks the report), cited claims only, reproducible scores.

---

# Part B: How it is built

## Slide 4: System Architecture & Pipeline
- **Diagram:** React UI → FastAPI → LangGraph state machine → agents (Groq / Gemini through LiteLLM, local spaCy NER, rule engines) → Postgres.
- **Pipeline (deep mode, 17 nodes):** web search → confidence indicator → market opportunity → competitor discovery → opportunity score → white space → SWOT → viability score → MVP ∥ GTM (parallel) → contradiction detector → experiments → action plan → assumption tracker → revenue models → confidence dashboard → verdict.
- **Quick mode** skips the strategy nodes (SWOT, viability, MVP, GTM, contradictions, experiments, action plan, revenue models) and returns core market validation only.
- **Speaker notes:** LLMs write the narrative sections. Everything numeric (scores, confidence, verdict) is deterministic Python over that output. Each node is timed and logged, and a failed node is recorded against its own section instead of aborting the run.
- **How the rest of the deck is ordered:** it follows this product: landing page, then each report tab in order, then delivery, then the platform.

---

## Slide 5: 18 Agents and Engines
- **Split:** 9 use a language model; 9 are plain code. Showing the split is the point.
- **AI:** market opportunity, competitor discovery, SWOT and risk, MVP planner, go-to-market, assumption tracker, revenue models, grounding verifier, advisor.
- **Rules:** web research, opportunity score, white-space analyzer, viability index, voice of the market, confidence dashboard, contradiction detector, experiments and action plan, verdict.
- **Naming:** a LangGraph pipeline of single-purpose agents, not an autonomous "swarm". Agents do not negotiate or pick their own tools.
- **Where to see it:** the landing page lists all 18 with the tools behind each.

---

# Part C: The product, in the order a founder sees it

## Slide 6: Landing Page, Input & the Report at a Glance
- **Landing page:** an interactive "How it works" (click a step to see what runs and which tools), the 18-agent grid, a tool-stack section and a comparison with general chatbots.
- **Input:** the hero takes the idea directly and carries it into the form; the form also offers four sample ideas that fill all three fields. A founder gives three things: the idea, the target customer, the problem.
- **The report opens in eight tabs:** Evidence, Market, Competitors, Customers, Gaps, Risks, Build & Ship, Roadmap. The next slides walk them in that order.
- **Why eight:** an earlier six-tab layout merged "Market & Rivals" and "Gaps & Exposure", which made two tabs very long. Splitting them lets each tab answer one question.

---

## Slide 7: Evidence Tab — Search Retrieval & Filtering
- **Angles:** `Market size & trends`, `Competitors`, `Industry news`, `Customer demand`, `How others solve this`.
- **Blended search:** Tavily and DuckDuckGo results are merged and deduplicated by URL, keeping the best score. The market-size and competitor angles use Tavily advanced search, and the top three competitor pages are read in full (Tavily Extract, 2,500 characters).
- **Product-first competitor queries:** the competitor angle searches for what the product does, not the customer's words (a freelancer invoicing idea moved from Upwork and Fiverr pages to FreshBooks, Harvest, Clockify and Avaza). Wikipedia and Hacker News serve as a zero-cost fallback only when neither returns.
- **Filtering:** `_EXCLUDED_DOMAINS` strips `arxiv.org` and generic directory and review aggregators (for example `competitors.app`, `alternativeto.net`, `saashub.com`, `trustradius.com`) that keyword-match almost any query without being about the idea. Low-signal Wikipedia page shapes are filtered too.
- **What the tab shows:** every source with its relevance, angle and date where known. Everything later in the report cites these sources by id.

---

## Slide 8: Competitors Tab — Discovery from Multiple Sources
- **Design:** competitors are no longer taken from one place. Five kinds of source are combined, and the result is merged and de-duplicated.
  1. **The web search results** (the blended Tavily + DuckDuckGo evidence from Slide 7), plus **the App Store's own search** for what the product does, added as ordinary cited sources (apps sharing at least two topic words with the idea, at most five).
  2. **Local spaCy NER** (`en_core_web_sm`) always runs over the snippets at no API cost. A denylist and a product-context test remove generic words mislabelled as companies.
  3. **An LLM discovery pass** (`gpt-oss-20b` first) reads richer source text and proposes rivals with an offering, a gap, strengths and weaknesses.
  4. **Public APIs for enrichment:** Product Hunt, the iTunes Search API (rating, price, artwork) and Wikidata (descriptions). A record attaches only when the competitor's name appears in the record's own title, so a lookalike cannot attach the wrong logo or rating.
  5. **Deterministic fallbacks** (a rule-built comparison matrix and profile defaults) when the model cannot produce one.
- **Grounding:** a rival must cite a valid source id. The stricter rule that its name also appear in that source's text was relaxed because it discarded real rivals the model knew from context.
- **History worth telling:** discovery began as an LLM agent, moved to NER-only to save free-tier quota, then became a multi-source merge once richer output mattered more than the saving.

---

## Slide 9: Competitors Tab — Direct vs Indirect, Matrix & Positioning
- **Mapping:** each rival is labelled **direct** (shares at least two distinct topic stems with the idea, ignoring the target-customer words), **indirect** (shares one), or left unlabelled. Competitor cards group by label and show a logo and one line of real data where enrichment found it.
- **Comparison matrix:** the idea against up to 8 rivals (direct first) across 6 to 8 rows. The AI-written matrix is topped up to at least 6 rows, and when the model is unavailable the rule-based fallback builds up to 8 rows from real data (price, feature breadth, positioning, what it offers, business model, strength, weakness, customer rating, founding year). The idea's own cells say "pre-launch" and never claim a price.
- **Positioning grid:** Price (`low/mid/high`) × Feature Breadth (`narrow/moderate/broad`). Rivals without price evidence land on `"unknown"` rather than being guessed.
- **Honest limit:** classification can under-label a rival when its source text is thin; a real but off-topic company is a relevance judgement the rule path cannot make.

---

## Slide 10: Market Tab — Sizing, Trends & Viability
- **Engine:** Groq `qwen/qwen3.8-27b` (with fallbacks, see Slide 21).
- **Outputs:** market-size narrative, **TAM / SAM / SOM** tiers, trends and customer segments, all carrying `sourceIds`.
- **TAM is always sourced** or hidden. **SAM and SOM** are shown as sourced figures when a source states them. When none does but a TAM exists, the model may give an **estimate**, shown with an "Estimate" badge, a dashed card, no citation and the assumption written out (for example, "assumes 20% of the TAM is reachable"). An estimate is never shown as sourced and never created without a TAM.
- **Viability breakdown:** five dynamics, from demand urgency to capital efficiency, shown as a breakdown beside the headline score.
- **Grounding:** a verification pass strips citations whose source does not support the claim.

---

## Slide 11: Customers Tab — Segments & Voice of the Market
- **Segments:** up to four, each with pain points, motivations and buying behaviour, cited to sources. Where the sources say nothing about buying behaviour the report says so rather than guessing.
- **Voice of the market:** a rule-based step pulls verbatim customer quotes from the sources and ties each to where it came from, so a founder reads real words, not a summary.
- **When evidence is missing:** if no customer-demand sources were collected, the tab says segments could not be grounded in real data for this run.

---

## Slide 12: Gaps Tab — White Space & Entry Wedge
- **White space:** a rule-based step triangulates customer pain points against competitor coverage to surface openings where need is real and coverage is weak.
- **Entry wedge:** a strategic-wedge blueprint suggests how to enter, with a conviction percentage and the key risk.
- **No model call:** this tab is computed from the Customers and Competitors results, so its quality follows theirs.

---

## Slide 13: Risks Tab — SWOT, Bear Case, Assumptions & Contradictions
- **SWOT and risk (AI):** strengths, weaknesses, opportunities and threats, each claim tagged Grounded or Inferred.
- **Bear case:** the investor objections drawn from the SWOT, so a founder meets the hard questions first.
- **Assumption tracker (AI):** the riskiest hidden assumptions and how to test each.
- **Contradiction detector (rules):** flags places where sections disagree, for example strong growth signals against weak customer-demand evidence. Shown as a banner above the report and as "Tension flags" in the PDF.

---

## Slide 14: Build & Ship Tab — MVP, Revenue Models & Go-to-Market
- **MVP planner (AI):** what to build first, and what can wait. **Go-to-market (AI):** positioning, channels and the first-customer approach. The two run **in parallel**.
- **Revenue models (AI):** two to three monetisation models that fit the market, each with a fit rating, pricing range and companies that use it.
- **Revenue fallback:** if the model call fails, the section is built from how the competitors found describe their own pricing (subscription, freemium, usage-based and so on), labelled as inferred from competitor pricing. Before this fix the section silently came back empty.

---

## Slide 15: Roadmap Tab — Timeline, Experiments & Action Plan
- **Build timeline:** a delivery roadmap for the MVP.
- **Validation plan (rules):** the top risks are turned into experiments with a hypothesis, method and success metric, then into a **7, 30 and 90 day action plan**.
- **Why it matters:** the report ends with what to do next, not only a verdict.

---

## Slide 16: Trusting the Result — Grounded vs Inferred & Confidence
- **Grounded vs Inferred:** each claim is tagged. Grounded means it cites a source that a verification pass accepted; Inferred means the model reasoned it, and it is listed as an assumption to test.
- **Headline confidence:** % of the sources the analysis actually **cites** whose relevance score is ≥ 0.5. It used to be computed over the whole raw search pool, which diluted it toward zero; see the [methodology doc](confidence-and-evidence-scoring-methodology.md).
- **Breakdown tiles:** source coverage, cross-source agreement, direct evidence, average relevance, source recency.
- **Honest meaning:** Grounded is not the same as true. The source itself may be wrong or out of date.

---

## Slide 17: Scores & the Verdict
- **Opportunity Score:** `clamp(marketSizeScore[0-40] + growthScore[0-30] + competitionScore[0-30], 0, 100)` (see doc 15).
- **Market Viability Score:** `0.4·marketDemand + 0.3·(100 − executionRisk) + 0.3·growthVelocity`. Two more axes, **competitionClarity** and **timing**, are reported alongside but left out of the headline because they measure how much is known, not whether the news is good.
- **Verdict:** deterministic *Pursue / Validate first / Rethink* with the reasons that decided it and one next step.
- **Open item:** the weights are documented but not yet calibrated against a labelled set of ideas.

---

## Slide 18: The Advisor Chat
- **What it is:** a follow-up chat grounded in the founder's own report and its decision history, so answers refer to this idea, not a generic one.
- **Searches only when needed:** it looks the web up again only when the question asks for something current (latest, pricing now, new competitors); otherwise it answers from the report.
- **Jumps to the evidence:** a question like "who are my competitors?" opens the Competitors tab at the section that answers it.
- **Model:** runs on Gemini so it does not spend the Groq quota the pipeline needs.

---

## Slide 19: Delivery — PDF & Email
- **PDF:** built on the server with **ReportLab**, typically 15 to 25 pages, and it prints everything the eight tabs show. Charts: evidence-confidence and source-agreement bars, a viability radar, a risk heat-map, a price-by-breadth positioning chart and a delivery timeline. Content: verdict, TAM/SAM/SOM (each marked Sourced or Estimate), market trends, segments, competitor profiles, the idea-versus-rivals comparison table, SWOT and bear case, white space, wedges, MVP, roadmap, assumptions, experiments, economics, go-to-market, revenue models, the 90-day plan, and an evidence log of every source with its excerpt. An "About this report" box says where a section used a rule-based fallback. Roadmap, economics and experiments carry an "Estimate" badge.
- **Email:** sent through **SendGrid's HTTP API** (chosen because the free host blocks SMTP ports). The email carries the report summary and a link to view it again. It does not attach the PDF; the PDF is a separate download.
- **Why email exists:** a run that cannot finish on the free quotas within about a minute continues in the background and is emailed when ready (see Slide 21).
- **Sharing:** a report link is a random id that works without sign-in, so anyone holding it can open that report.

---

# Part D: The platform around it

## Slide 20: Accounts, Dashboards & Security
- **Accounts:** optional email + password (bcrypt, 30-day JWT), Google sign-in, and password reset by a single-use emailed link (30 minutes, only a hash stored; the endpoint answers the same whether or not the email has an account). Anonymous validation still works.
- **Account menu:** History, Compare ideas, Dashboard, and (admins only) Platform health.
- **Founder Dashboard:** Overview, Comparison matrix, Validation history, Score trends.
- **Admin Platform Health:** validations per day, cache hit rate, API success rate, deep-analysis rate, latency by node, model usage, recent errors and email delivery, backed by a durable `events` log. Admin access comes only from the `ADMIN_EMAILS` environment variable.
- **Retention:** sessions 7 days, response cache 30 minutes, background jobs 2 hours, events 90 days; per-IP rate limits on auth, validate, chat, export and email.

---

## Slide 21: Reliability — Fallback Chain & Fallbacks
- **Chain:** `groq/qwen/qwen3.8-27b` → `groq/openai/gpt-oss-20b` → `groq/openai/gpt-oss-120b` → `gemini/gemini-3.6-flash` → `gemini/gemini-3.8-flash`.
- **Load split:** each agent starts on its own model so no single free quota carries the run: market on Qwen; competitor discovery, MVP, the assumption tracker and the verifier on `gpt-oss-20b`; SWOT, go-to-market and revenue models on `gpt-oss-120b`; the advisor on Gemini 3.6. Six agents used to share Qwen's 1,000-tokens-a-minute bucket. Reasoned from tokens and timing; only partly checked live.
- **Switch triggers:** rate limits, missing models, provider errors, **and responses that fail per-attempt shape validation** (for example unparseable JSON). A common cause was a cut-off answer: the gpt-oss models spend part of `max_tokens` on hidden reasoning, so token budgets are now scaled per model (SWOT needed about 1,100-2,200 tokens against a 900 limit).
- **Provider limits that shaped it:** Qwen has a hard 1,000 output-token per minute cap, so its calls stay under about 950 tokens; the `gpt-oss` models have 8,000 tokens per minute and a daily cap; Gemini's free tier allows about 20 requests a day per model.
- **Last resort:** a local Ollama model (only where one runs), then one cloud retry after a cooldown, then a labelled deterministic fallback. Where a local model exists but no email is on file, the user is asked for an email so the slower run can be sent to them.
- **Cache:** identical requests are cached for 30 minutes, and only successful responses are cached, so a cached result is never a hidden failure. A second lookup cache keeps search results (12 h), page extracts (7 d), App Store results (24 h) and company facts (30 d): a repeat run measured 20.4 s down to 2.8 s with no paid calls, while a different idea in the same space saved nothing.

---

## Slide 22: Tools & Services Used
- **Orchestration and agents:** LangGraph, CrewAI (one single-task agent per AI section), LiteLLM (one interface to Groq and Gemini).
- **Evidence:** Tavily, DuckDuckGo, spaCy, Product Hunt, iTunes Search, Wikidata.
- **Delivery:** **ReportLab** (PDF), **SendGrid HTTP API** (email), FastAPI (serves it all).
- **Accounts and storage:** PostgreSQL on Neon (SQLite locally) through SQLAlchemy, bcrypt and JWT, optional Google sign-in.
- **Frontend:** React 19, Vite, Tailwind 4, tested with Vitest. Backend and frontend both hosted on Render.

---

## Slide 23: Why Not Just Ask a Chatbot?
- **Fair framing:** assistants such as ChatGPT and Claude reason well and can browse. The difference is how checkable the answer is.
- **Evidence:** fixed five-angle search with every source listed, versus training data unless asked to search.
- **Claims:** each tagged Grounded or Inferred and verified, versus fluent text whether or not anything backs it.
- **Scoring:** computed by code and repeatable for the same evidence, versus whatever the model says that time.
- **Output and memory:** tabs, PDF, emailed copy, saved history and comparison, versus a chat reply per conversation.
- **Caution when presenting:** compare behaviours we can show; avoid claims about other products we have not tested.

---

# Part E: Evidence and honesty

## Slide 24: Verification, Bugs Found & User Test
- **Tested domains:** Student Budgeting, Coffee Subscriptions, Meal Prep, Photo Invoicing, Fintech, Health Journaling, Smart Water Bottle.
- **Method lesson:** live search varies run to run, so one good or bad run proves little; fixes were checked across several ideas.
- **Defects found only by live testing:** fallback chain stopping early, confidence diluted by the raw search pool, TAM/SAM/SOM computed but not shown, admin access lost on redeploy, junk competitor names, a positioning grid that never rendered, and revenue models silently empty when quota ran out. Each has a regression test.
- **Partial failure:** a failed section returns an inline error card; the rest of the report still renders.
- **Suites:** over 500 backend and over 100 frontend tests. The backend suite runs keyless through `scripts/run_tests.py`; run plainly it loaded real keys and spent free-tier quota.
- **Informal user test (5 people):** 2 got the report on screen; 3 were asked for an email and each received the full report by email in roughly 4 to 5 minutes. This is what the free-tier quota fallback looks like to a real user. It is five people informally observed, not a measured benchmark.
- Details: [milestone2-verification.md](milestone2-verification.md), [milestone4-verification.md](milestone4-verification.md).

---

## Slide 25: Cost & Latency
- **Free-tier operation:** Groq and Gemini free tiers, free search and enrichment APIs, Render free tier.
- **Latency:** the original single-LLM pipeline measured about 10 s *(re-measure: deep mode now runs many more LLM-backed steps; quick mode is the fast path)*.
- **Per-request cost:** about $0.00067 on paid tiers at Milestone 2 *(re-measure)*.
- **Real constraint:** quota, not money. Heavy use exhausts the free per-minute and daily limits, which is why the fallbacks on Slide 21 exist.

---

## Slide 26: Limitations & Future Work
- **Not built yet:** a calibration of the score weights against labelled ideas; a measured competitor-recall figure; a written scaling plan beyond free tiers; progressive rendering of sections as they finish; a saved real example report on the landing page.
- **Accuracy:** results vary run to run because retrieval uses live search; agents mostly read trimmed snippets, with deeper content only for the market-size and competitor angles (Tavily advanced search, and full-page Extract for the top three competitor sources, capped at 2,500 characters); "Grounded" means a claim cites an accepted source, not that the source is true; SAM and SOM estimates are the model's own working and are labelled as such; scores are reasoned, not calibrated; tested on seven industries, so niche or non-English markets are unproven.
- **Quota exposure:** on free tiers, heavy use pushes runs onto the slower email path (3 of 5 testers saw it).
- **Operational:** sessions expire after 7 days; Render's free Postgres expires after 30 days; a free host sleeps when idle and the free database auto-suspends, which slows the first sign-in; no email verification yet (password reset was added on 2026-10-02).
- **Technical:** the local-model fallback needs real GPU hardware; rival classification under-labels on thin text.
- Full list: [known-limitations-and-future-work.md](known-limitations-and-future-work.md), [scaling-options.md](scaling-options.md).

---

## Slide 27: Conclusion & Defense Q&A
- **Summary:** a working multi-agent startup validator that combines live web retrieval, multi-source competitor discovery, cited analysis and deterministic scoring, delivered as an eight-tab report, a PDF, an email and an advisor chat, with accounts, dashboards and an admin view.
- **Likely questions to prepare:**
  - How is confidence computed and why trust it?
  - What happens when every LLM is rate-limited? (Slides 21 and 24)
  - Why did competitor discovery become multi-source? (Slide 8)
  - Where do SAM and SOM come from if no source states them? (Slide 10)
  - What is the difference between your pipeline and a "swarm"? (Slide 5)
  - What is not done yet? (Slide 26)
  - How is admin access controlled, and what data is kept for how long? (Slide 20)
