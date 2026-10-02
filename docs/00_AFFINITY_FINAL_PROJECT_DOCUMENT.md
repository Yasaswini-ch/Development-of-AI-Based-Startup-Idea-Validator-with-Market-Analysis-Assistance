# Affinity: Final Project Document

**Project:** Affinity, an AI-based startup idea validator with market analysis assistance
**Version:** 1.0, 2 October 2026, written against the `staging` branch
**Purpose:** one document that describes the whole project as it stands today. The numbered
chapters (`01` to `23`) go deeper on each part; this file is the map and the summary.

> **How to read this.** Where a statement is a measurement from an earlier milestone it is
> marked *(re-measure)*. Where something is not built, it is listed in
> [section 13](#13-limitations-and-what-is-not-done-yet) rather than implied. Nothing in this document
> describes a feature the code does not have.

---

## Contents
1. [What Affinity is](#1-what-affinity-is)
2. [The problem and the approach](#2-the-problem-and-the-approach)
3. [What a founder gets](#3-what-a-founder-gets)
4. [System architecture](#4-system-architecture)
5. [The pipeline, stage by stage](#5-the-pipeline-stage-by-stage)
6. [Agents and engines](#6-agents-and-engines)
7. [Competitor discovery](#7-competitor-discovery)
8. [Scoring and evidence](#8-scoring-and-evidence)
9. [Reliability under free-tier limits](#9-reliability-under-free-tier-limits)
10. [Tools and services used](#10-tools-and-services-used)
11. [How it differs from asking a chatbot](#11-how-it-differs-from-asking-a-chatbot)
12. [Accounts, data and security](#12-accounts-data-and-security)
13. [Limitations and what is not done yet](#13-limitations-and-what-is-not-done-yet)
14. [Testing and verification](#14-testing-and-verification)
15. [Team and milestones](#15-team-and-milestones)
16. [Running it locally and deploying](#16-running-it-locally-and-deploying)
17. [Document map](#17-document-map)

---

## 1. What Affinity is

Affinity validates a startup idea. A founder gives three things: the **idea**, the **target
customer** and the **problem** it solves. The backend searches the live web, runs a pipeline
of analysis steps, and returns a source-cited report with a verdict of **Pursue**,
**Validate first** or **Rethink**.

The product claim is narrow on purpose: every market claim in the report is tied to a source
the founder can open, and every number (scores, confidence, verdict) is computed by plain code
from that evidence, not asserted by a language model.

## 2. The problem and the approach

Most early startups fail because nobody needed what was built. Checking that first is slow
by hand and unreliable with a general chatbot, which answers fluently whether or not
anything backs the answer.

Affinity's approach has four parts:

1. **Retrieve first.** Search the web across five fixed angles before any reasoning starts.
2. **Cite everything.** Each claim carries source ids, or is labelled *Inferred*.
3. **Compute the numbers.** Scores, confidence and the verdict come from deterministic code.
4. **Fail partially, not totally.** One failed section shows an inline message while the
   rest of the report still renders.

## 3. What a founder gets

The report opens in **eight tabs**:

| Tab | Contents |
|---|---|
| Evidence | Every source found, with relevance, angle and date where known |
| Market | Market signal, TAM / SAM / SOM (TAM sourced; SAM and SOM sourced or a labelled estimate), viability breakdown |
| Competitors | Rivals found, each labelled direct or indirect, with logo, pricing and a comparison table against the idea |
| Customers | Customer segments, pain points, and verbatim quotes from the sources |
| Gaps | White-space analysis: where customer pain meets weak competitor coverage |
| Risks | Strengths and exposure, the bear case (investor objections), key assumptions to test |
| Build & Ship | MVP blueprint, revenue models, go-to-market |
| Roadmap | Build timeline, validation experiments, 7 / 30 / 90 day plan |

Around the report:

- A **verdict card** with the score and the reasons that decided it.
- A **confidence dashboard** (source coverage, cross-source agreement, direct evidence,
  relevance, recency) and a **contradiction banner** when sections disagree.
- A **chat advisor** that answers follow-up questions from the report and jumps to the
  section it used.
- **PDF export** and **email delivery** of the finished report.
- For signed-in users: **history**, **compare ideas**, a **dashboard**, and for admins a
  **platform health** view.

The landing page explains the product with an interactive "How it works", a grid of every
agent and engine with the tools behind each, a tech-stack section and a comparison with
general chatbots. The hero accepts an idea directly, and the form offers sample ideas.

## 4. System architecture

```
React 19 + Vite + Tailwind 4   (frontend/)
        |  HTTPS, JSON
FastAPI                         (backend/main.py)
        |
LangGraph state machine         (backend/agent/graph.py)
   |-- web retrieval            Tavily + DuckDuckGo
   |-- LLM agents (CrewAI)      Groq and Gemini through LiteLLM
   |-- local NER                spaCy en_core_web_sm
   |-- rule-based engines       plain Python
        |
PostgreSQL (Neon) in production, SQLite locally    (SQLAlchemy)
```

- **Frontend:** React 19, Vite, Tailwind 4. Tests use Vitest and Testing Library; lint uses oxlint.
- **Backend:** FastAPI with a LangGraph pipeline. Each LLM-backed agent is a single-agent
  CrewAI crew with one task and no tools.
- **State:** the in-progress result lives in the browser's `sessionStorage`; accounts,
  sessions, jobs, cache and events live in the database.

Deeper reading: [architecture.md](architecture.md), [04 system topology](04_AFFINITY_SYSTEM_TOPOLOGY_AND_DESIGN.md).

## 5. The pipeline, stage by stage

Seventeen graph nodes run in this order in deep mode (step 9 is two nodes that run in parallel):

1. **web_search**: five angles, Tavily and DuckDuckGo blended and deduplicated by URL
2. **confidence_indicator**: counts sources that describe growth or competitive pressure
3. **market_opportunity** *(AI)*: market size, trends, customer segments
4. **competitor_discovery** *(AI + local NER)*: rivals, labelled direct or indirect
5. **opportunity_score** *(rules)*
6. **white_space** *(rules)*
7. **swot_analysis** *(AI)*
8. **viability_score** *(rules)*
9. **mvp_recommendation** *(AI)* and **gtm_strategy** *(AI)*, **in parallel**
10. **contradiction_detector** *(rules)*
11. **experiment_generator** *(rules)*
12. **action_plan** *(rules)*
13. **assumption_tracker** *(AI)*
14. **revenue_models** *(AI, with a rule-based fallback)*
15. **confidence_dashboard** *(rules)*
16. **compute_verdict** *(rules)*

Quick mode runs only market, competitor and white-space analysis. Each node is timed and
logged; a node's failure is recorded against its own section and does not abort the rest.

## 6. Agents and engines

Eighteen named agents and engines appear on the landing page: nine use a language model and
nine are plain code. The split matters, and is stated that way on purpose.

| Kind | Name | Job |
|---|---|---|
| Rules | Web research | Searches five angles, filters duplicates and low-signal sites |
| AI | Market opportunity | Sizes the market, spots trends, builds customer segments |
| AI | Competitor discovery | Finds rivals, labels them, compares them with the idea |
| AI | SWOT and risk | Strengths, weaknesses, opportunities, threats, each claim Grounded or Inferred |
| AI | MVP planner | What to build first |
| AI | Go-to-market | Positioning, channels, first customers |
| AI | Assumption tracker | The riskiest hidden assumptions and how to test them |
| AI | Revenue models | Monetisation models that fit this market |
| AI | Grounding verifier | Checks each claim is supported by the source it cites |
| AI | Advisor | Follow-up chat, searches again only when it needs fresh data |
| Rules | Opportunity score | 0 to 100 from market size and growth signals |
| Rules | White-space analyzer | Triangulates customer pain against competitor gaps |
| Rules | Viability index | Five dynamics combined into one score |
| Rules | Voice of the market | Verbatim customer quotes tied to their sources |
| Rules | Confidence dashboard | Coverage, agreement, direct evidence, relevance |
| Rules | Contradiction detector | Flags sections that disagree |
| Rules | Experiments and action plan | Turns top risks into experiments and a 7 / 30 / 90 day plan |
| Rules | Verdict | Pursue, Validate first or Rethink, with reasons |

**Naming:** this is a LangGraph pipeline of single-purpose agents and rule engines. It is not
described as an autonomous "swarm"; agents do not negotiate or choose their own tools.

## 7. Competitor discovery

This was the most reworked part of the project, and its history explains its design.
Competitors are now discovered from **several sources combined**, not one: the web search
results, local NER, an LLM pass, three public APIs and rule-based fallbacks. The merged list
is de-duplicated before it is enriched and classified.

1. **Local spaCy NER** always runs first over the search snippets, at no API cost. Generic
   words mislabelled as organisations ("History", "Windows", "Reply") are removed by a
   denylist and a product-context test for single-word names.
2. **LLM discovery** (`gpt-oss-20b` first) reads richer source text and proposes rivals with
   a short offering, a gap, strengths and weaknesses. The two lists are merged.
3. **Enrichment** adds free public data where a match is certain: Product Hunt, the iTunes
   search API (rating, price, artwork) and Wikidata. A name must appear in the matched
   record's own title, so a lookalike cannot attach the wrong logo or rating.
4. **Direct or indirect.** Each rival is classified from its own local text: *direct* if it
   shares at least two distinct topic stems with the idea (excluding the target-customer
   words), *indirect* if it shares one, otherwise unlabelled. The cards group by this.
5. **Comparison matrix.** A table of the idea against each rival, with a deterministic
   fallback when the model cannot produce one.
6. **Grounding.** A competitor must cite a valid source id. The earlier rule that its name
   also appear in that source's text was relaxed, because it discarded real rivals the model
   knew from the page's context.

**Known limit:** classification can under-label rivals when a source gives little text. The
LLM path does better than the rule path there. A real company that is off-topic for the idea
is a relevance judgement the rule path cannot make. See [14](14_AFFINITY_COMPETITOR_GRID_AND_POSITIONING_PARSER.md).

## 8. Scoring and evidence

All of the following are computed by code, so the same evidence gives the same numbers.

- **Opportunity score:** `clamp(marketSizeScore[0-40] + growthScore[0-30] + competitionScore[0-30], 0, 100)`.
  See [15](15_AFFINITY_OPPORTUNITY_SCORE_MATHEMATICAL_MODEL.md).
- **Market viability:** `0.4 * marketDemand + 0.3 * (100 - executionRisk) + 0.3 * growthVelocity`.
  Two further axes, competition clarity and timing, are shown but kept out of the headline,
  because they measure how much is known, not whether the news is good.
- **Confidence:** the share of the sources the analysis actually cites that clear a relevance
  threshold, plus coverage, cross-source agreement, direct-evidence ratio and recency. See
  [confidence methodology](confidence-and-evidence-scoring-methodology.md).
- **Grounded vs Inferred:** each claim is tagged. Grounded means it cites a source that a
  verification pass accepted; Inferred means the model reasoned it, and it is listed as an
  assumption to test.
- **Verdict:** a threshold decision with the reasons that decided it and one next step.

## 9. Reliability under free-tier limits

Affinity runs on free tiers, so rate limits are the main operational risk.

- **Model chain:** `groq/qwen/qwen3.8-27b`, then `groq/openai/gpt-oss-20b`,
  `groq/openai/gpt-oss-120b`, `gemini/gemini-3.6-flash`, `gemini/gemini-3.8-flash`. A
  call moves on for rate limits, missing models, provider errors, **and** responses whose
  JSON fails shape validation.
- **Load is split across models** so no single quota carries everything: competitor
  discovery starts on `gpt-oss-20b`, go-to-market on `gpt-oss-120b`, and the advisor on
  Gemini.
- **Provider limits that shaped the design:** the Qwen model has a hard 1,000 output-token
  per-minute cap, so its calls are kept under about 950 tokens; the `gpt-oss` models have an
  8,000 tokens-per-minute and a daily cap; Gemini's free tier allows about 20 requests a day
  per model.
- **When every cloud model is exhausted:** a local Ollama model is tried only where one
  exists. Otherwise a section shows a clearly labelled deterministic fallback built from the
  evidence already gathered. Where a local model exists but no email is on file, the user
  is asked for an email so the slower run can be sent to them.
- **Revenue models** now have a rule-based fallback: if the model call fails, the section is
  built from how the competitors found describe their own pricing (subscription, freemium,
  usage-based and so on), labelled as inferred from competitor pricing. Before this fix the
  section simply came back empty.
- **Caching:** identical requests are cached for 30 minutes, and only successful responses
  (no section errors) are cached, so a cached result is never a hidden failure.

## 10. Tools and services used

| Area | Tool | Used for |
|---|---|---|
| Orchestration | LangGraph | Runs the pipeline as a graph, MVP and go-to-market in parallel |
| Agents | CrewAI | One single-task agent per AI section |
| Model access | LiteLLM | One interface to Groq and Gemini, with fallback |
| Models | Groq, Gemini (Ollama locally) | Reasoning steps |
| Search | Tavily, DuckDuckGo | Live web retrieval |
| Entity extraction | spaCy | Local competitor-name extraction |
| Enrichment | Product Hunt, iTunes Search, Wikidata | Ratings, pricing, logos, descriptions |
| API | FastAPI | HTTP API, job status, rate limiting |
| PDF | ReportLab | Builds the downloadable report on the server |
| Email | SendGrid HTTP API | Emails the report; chosen because the host blocks SMTP ports |
| Database | PostgreSQL (Neon), SQLite locally, via SQLAlchemy | Accounts, sessions, jobs, cache, events |
| Auth | bcrypt, JWT, Google sign-in | Passwords, sessions, optional one-click sign-in |
| Frontend | React 19, Vite, Tailwind 4 | The application |
| Hosting | Render (web service for the API, static site for the frontend) | Deployment |

## 11. How it differs from asking a chatbot

General assistants such as ChatGPT and Claude reason well and can browse, and they remain
useful alongside this. The difference is how checkable the answer is.

| | Affinity | A general chatbot |
|---|---|---|
| Evidence | Searches five fixed angles and lists every source | Answers from training data unless asked to search |
| Claims | Each tagged Grounded or Inferred, with a verification pass | Read the same whether or not anything backs them |
| Scoring | Computed by code, repeatable for the same evidence | Whatever the model says that time |
| Competitors | Found in the sources, labelled direct or indirect | A list from memory |
| Output | Tabs, PDF, emailed copy | A chat reply to copy out |
| History | Saves runs and compares ideas | Each chat starts over |

The comparison deliberately avoids claims about other products that were not verified.

## 12. Accounts, data and security

- **Accounts are optional.** Anonymous use works; signing in saves history.
- **Auth:** bcrypt password hashes, HS256 JWT valid 30 days, Google sign-in verified on the
  server, and password reset by emailed single-use link (30 minutes, only a hash stored). Per-IP rate limits cover sign-in, validation, chat, export and email.
- **Admin access** comes only from the `ADMIN_EMAILS` environment variable. There is no
  self-service route.
- **Retention:** validation sessions expire after 7 days (200-row cap), the response cache
  after 30 minutes, events after 90 days. Accounts persist.
- **Share links:** a report's session id is a random UUID that works as a link, so report,
  chat and PDF endpoints do not require sign-in. Anyone with the link can open that report.
- **Secrets** live in environment variables and are never committed.

See [security-privacy-ethics.md](security-privacy-ethics.md).

## 13. Limitations and what is not done yet

Stated plainly so nobody has to discover it. Section 13.1 is the set of known limits of how
the system behaves; 13.2 is work that was asked for or planned and is not finished.

### 13.1 Limitations

**Reliability and speed**

- **Dependence on free tiers.** The pipeline relies on free Groq and Gemini quotas. Under
  load or after heavy use the cloud models are exhausted, and a run then takes the slower
  email path instead of returning on screen (see the user test in section 14.2, where this
  happened to three of five testers). Free tiers can also change or disappear without notice.
- **Answer quality depends on which model answered.** A section produced by a fallback model,
  or by the rule-based fallback, is thinner than one from the first-choice model. Fallback
  output is labelled as degraded, but it is still weaker.
- **The email path is slow by design.** A run that goes to the local or retried path takes
  minutes, and the founder must wait for an email rather than see the result.
- **Cold starts.** The free web host sleeps when idle and the free database auto-suspends, so
  the first request or sign-in after a quiet spell can take up to a minute.
- **No capacity planning.** Concurrent users share the same provider quotas; there is no
  queue, priority or per-user budget beyond per-IP rate limits.

**Accuracy and evidence**

- **Results vary between runs.** Retrieval uses live web search, so the same idea can return
  different sources, competitors and numbers on different days. A single run is not a
  reproducible measurement. The scoring code is deterministic only for a given set of evidence.
- **The analysis reads snippets, not whole pages.** Each source is trimmed to roughly 1,500
  characters before it reaches an agent, so a fact deeper in a page is missed.
- **"Grounded" is not "true".** It means a claim cites a source that a verification pass
  accepted as supporting it. The source itself may be wrong, biased or out of date.
- **Market sizing is only as good as the sources.** TAM is shown only where a source states
  the figure. SAM and SOM are shown as sourced figures when a source states them; otherwise,
  if a TAM exists, the model may give an **estimate** from the TAM and the target customer. An
  estimate is badged "Estimate", has no citation, shows its assumption and is never created
  without a TAM. It is the model's own working, not evidence, and a founder should treat it as
  a starting point to check. Before this was added, SAM and SOM were almost always hidden.
- **Competitor results are imperfect.** Rival classification can under-label a company when
  its source text is thin, and a real company that is off-topic for the idea can still appear.
  Price and feature-breadth labels come from text heuristics and are often "unknown".
  Competitor enrichment (ratings, logos) only attaches when the name matches exactly, so some
  rivals have none.
- **Scores and the verdict are not calibrated.** The weights are reasoned and documented, not
  tuned against ideas whose real outcomes are known. The verdict is decision support, not
  investment advice or a prediction of success.
- **Tested on a limited set.** Live verification covered seven industries and a small number
  of testers. Niche, non-English or offline markets, where the web has little to say, are
  untested and will return less evidence.

**Product and operations**

- **No charts in the PDF**, and sections appear only once the whole run finishes.
- **No email verification** for accounts. Password reset was added on 2026-10-02: a single-use
  link, valid 30 minutes, emailed through SendGrid. It does not sign out sessions already issued.
- **Reports expire.** Validation sessions are kept for 7 days, even for signed-in users, and
  a free Render Postgres database expires 30 days after creation.
- **Share links are open.** Anyone holding a report's link can view that report, its PDF and
  its chat, without signing in.
- **The local-model fallback is impractical without real hardware**, so hosted deployments
  do not use it.

### 13.2 Not done yet

Work that was asked for or planned and is not finished:

- **PDF charts.** The PDF is built with ReportLab as structured text and tables; it has no
  charts. A mentor asked for charts, and this is open.
- **Real example report on the landing page.** The "See an example report" feature and hero
  input are built but not shipped: a real saved run could not be captured because the free
  model quotas were exhausted, and a placeholder was not used in its place.
- **Scoring review.** A mentor asked for a review of how scores are weighted. The formulas
  are documented but have not been calibrated against a labelled set of ideas.
- **Competitor volume.** The mentor suggestion to find more competitors is partly met (an
  LLM pass now adds to NER) but there is no measured recall figure.
- **Cloud scaling and limits.** A write-up of how it scales beyond the free tiers is
  pending; the practical limits are the provider quotas in section 9, a free web host that
  sleeps when idle, and a free database that auto-suspends. See [scaling-options.md](scaling-options.md).
- **Progressive rendering** (showing sections as each finishes) was deliberately deferred.
- **Full list** of limits and future work: [known-limitations-and-future-work.md](known-limitations-and-future-work.md).
- **Environment-dependent tests.** Two backend tests fail when real API keys are present in
  `.env`, because they assume a keyless setup. They also fail on earlier commits.

## 14. Testing and verification

### 14.1 Automated and live verification

- **Backend:** roughly 520 unit and integration tests (`python -m unittest discover -s tests`).
- **Frontend:** about 100 Vitest tests covering the report tabs, landing page, competitor
  cards, count-up animation, chat routing and the new components.
- **Live verification:** the app was run end to end against real searches and models across
  seven industries (budgeting, coffee, meal prep, invoicing, fintech, health journaling,
  smart water bottle). Several defects were found only this way: the model chain stopping
  early, confidence diluted by the raw search pool, market tiers computed but not shown,
  garbage competitor names, and a positioning grid that never rendered. Each now has a
  regression test. Results are in [milestone2-verification.md](milestone2-verification.md)
  and [milestone4-verification.md](milestone4-verification.md).
- **Lesson recorded:** NER output varies run to run because live search varies, so one good
  or bad run proves little. Fixes were checked across several ideas.

### 14.2 Informal user test

The app was tried by **five people**. Observed outcome, as reported by the tester:

| Outcome | People |
|---|---|
| Report returned on screen | 2 |
| Asked for an email, then received the full report by email | 3 |

Each of the three emailed reports arrived in roughly **4 to 5 minutes**.

What this shows, and what it does not:

- It matches the mechanism in section 9. When the free cloud quotas are exhausted the app
  asks for an email, runs the slower path in the background and sends the result, and that
  path completed for every tester who used it.
- Three of five people hitting the email path means that, on the free tiers, it is a common
  experience rather than a rare edge case. The 4 to 5 minute wait is the practical cost.
- It is **five people, informally observed**. It is not a measured success rate or a latency
  benchmark, and the exact timing was not logged per run. Treat it as an indication to be
  re-measured under controlled conditions, not as a result.


## 15. Team and milestones

| Member | Main areas |
|---|---|
| Yasaswini | Market and competitor agents, architecture, most backend and integration work |
| Yalene | Orchestration and partial-failure handling |
| Sashi | Opportunity score and confidence indicator |
| Anu Kumari | Frontend components |
| Varshini | Cross-industry validation testing and report |

| Milestone | Delivered |
|---|---|
| 1 | Five-angle retrieval, free search fallbacks, domain exclusion, first interface |
| 2 | Market agent, competitor discovery and positioning grid, agreement indicator, white space, opportunity score |
| 3 | SWOT, MVP, go-to-market, advisor chat, PostgreSQL and accounts, PDF export, comparison matrix |
| 4 | Email delivery, evidence and confidence layer, contradiction detector, experiments and action plan, Google sign-in |
| 5 | Analytics dashboards and role-based admin access |
| Latest | Multi-source competitor discovery (web, NER, LLM, public APIs; direct and indirect), eight-tab report, redesigned landing page, revenue-model fallback, labelled SAM/SOM estimates |

Contribution history is in the git log.

## 16. Running it locally and deploying

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env        # set GROQ_API_KEY; TAVILY_API_KEY optional
uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
cp .env.example .env        # VITE_API_URL=http://localhost:8000
npm run dev                 # http://localhost:5173
```

Practical notes:

- Running with `--reload` restarts the server on every code edit and kills any in-flight run.
- The frontend keeps the last result in `sessionStorage`; clear it when testing a change, or
  a stale result can appear.
- Deployment steps, environment variables and runbooks are in
  [09 cloud deployment](09_AFFINITY_CLOUD_DEPLOYMENT_AND_DEVOPS_RUNBOOKS.md) and
  [DEPLOYMENT.md](../DEPLOYMENT.md).

## 17. Document map

| Need | Read |
|---|---|
| Vision and problem | [01](01_AFFINITY_EXECUTIVE_OVERVIEW_AND_VISION.md), [02](02_AFFINITY_PROBLEM_STATEMENT_AND_CORE_OBJECTIVES.md) |
| Requirements | [03](03_AFFINITY_SOFTWARE_REQUIREMENTS_SPECIFICATION.md) |
| Design and agents | [04](04_AFFINITY_SYSTEM_TOPOLOGY_AND_DESIGN.md), [05](05_AFFINITY_AGENTIC_AI_AND_ML_ENGINE.md), [architecture.md](architecture.md) |
| Data and API | [06](06_AFFINITY_DATA_MODELS_AND_STATE_SCHEMAS.md), [07](07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md) |
| Testing | [08](08_AFFINITY_LIVE_VERIFICATION_AND_TEST_PROTOCOL.md) |
| Deployment | [09](09_AFFINITY_CLOUD_DEPLOYMENT_AND_DEVOPS_RUNBOOKS.md) |
| Using the app | [10](10_AFFINITY_USER_OPERATIONS_AND_DOSSIER_MANUAL.md) |
| Academic report | [11](11_AFFINITY_FINAL_CAPSTONE_PROJECT_THESIS.md) (older, from Milestone 2) |
| Presentation | [18](18_AFFINITY_ACADEMIC_VIVA_SLIDE_DECK_OUTLINE.md) |
| Cost and accuracy | [13](13_AFFINITY_UNIT_ECONOMICS_COST_AND_ACCURACY_METRICS.md) |
| Scoring maths | [15](15_AFFINITY_OPPORTUNITY_SCORE_MATHEMATICAL_MODEL.md) |
| Limits and future work | [known-limitations-and-future-work.md](known-limitations-and-future-work.md), [scaling-options.md](scaling-options.md) |
