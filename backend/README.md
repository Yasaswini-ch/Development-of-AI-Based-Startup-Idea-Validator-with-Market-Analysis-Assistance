# Backend

FastAPI service that runs the Affinity validation pipeline. Updated 2026-10-02.

- **Full API reference** (all 21 routes, auth, limits, failure responses):
  [`docs/07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md`](../docs/07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md)
- **System design and data contracts:** [`docs/architecture.md`](../docs/architecture.md)
- **Whole-project summary:** [`docs/00_AFFINITY_FINAL_PROJECT_DOCUMENT.md`](../docs/00_AFFINITY_FINAL_PROJECT_DOCUMENT.md)

## How it runs

A **LangGraph** state graph (`agent/graph.py`) wires 17 nodes. In deep mode they run in this
order:

`web_search` → `confidence_indicator` → `market_opportunity` → `competitor_discovery` →
`opportunity_score` → `white_space` → `swot_analysis` → `viability_score` →
(`mvp_recommendation` ∥ `gtm_strategy`, in parallel) → `contradiction_detector` →
`experiment_generator` → `action_plan` → `assumption_tracker` → `revenue_models` →
`confidence_dashboard` → `compute_verdict`.

Every node reads the Web Search step's results as context, so nothing re-searches. Each node
is timed and logged. `mode: "quick"` skips the strategy nodes (SWOT, viability, MVP, GTM,
contradictions, experiments, action plan, revenue models) and returns core market validation.

**Which steps use an LLM.** Nine of the 18 agents and engines call a language model, each as
a single-agent CrewAI crew with one task and no tools: market opportunity, competitor
discovery, SWOT and risk, MVP, go-to-market, assumptions, revenue models, the grounding
verifier and the advisor. The rest (web research, scoring, white space, viability, voice of
the market, confidence, contradictions, experiments and action plan, verdict) are plain
Python, so their numbers do not depend on a model.

**Competitor discovery combines several sources.** Local spaCy NER (`en_core_web_sm`) always
runs over the search snippets first, at no API cost. An LLM pass then adds rivals with an
offering, gap, strengths and weaknesses, and the two lists are merged. Product Hunt, the
iTunes Search API and Wikidata enrich matches where the name is certain. Each rival is
labelled direct or indirect from its own text. A deterministic matrix and profile fallback
covers a failed model call. See the module docstring in `agent/competitor_agent.py`.

**Failures are isolated.** A node that fails records its message under `errors.<section>`
and the rest of the report still returns. Only a failure of `web_search` itself (nothing to
reason over) fails the request with a `502`. Sections with a rule-based fallback (market
opportunity, SWOT, MVP, GTM, competitors, revenue models) return a result flagged
`"degraded": true` instead of coming back empty.

## Search

Tavily and DuckDuckGo results are blended and deduplicated by URL, keeping the best score. The
"Market size & trends" and "Competitors" angles use Tavily's advanced search, and the top three
Competitors results also get their full page text through Tavily Extract (capped at 2,500
characters, read only by the competitor LLM pass and never returned in the API response). These
use more credits per run; set `TAVILY_DEEP=0` to turn them off, and each falls back to normal
search if it fails. The competitor angle searches for what the product does (`retrieval._what_it_does`),
not the customer's words, and the App Store's own search adds rival apps as cited sources
(`ITUNES_DISCOVERY=0` turns that off). `agent/web_cache.py` caches these lookups and company facts
between runs (`WEB_CACHE=0` bypasses it);
Wikipedia and Hacker News serve as a zero-cost fallback only when neither returns. Each
idea is expanded into five angles (market size and trends, competitors, industry news,
customer demand, how others solve this). Academic domains and generic directory or review
aggregators are excluded (`_EXCLUDED_DOMAINS` in `agent/retrieval.py`).

## LLM routing

`agent/llm.py` routes through Groq and Gemini via LiteLLM. The chain starts at
`groq/qwen/qwen3.8-27b`, then `groq/openai/gpt-oss-20b`, `groq/openai/gpt-oss-120b`,
`gemini/gemini-3.6-flash` and `gemini/gemini-3.8-flash`.
`kickoff_with_fallback()` moves to the next model immediately on a rate limit, a missing
model, a provider error, or a response whose JSON fails the caller's shape check.

- **Load is split** so no single quota carries the whole run. Each agent starts on its own model
  (`AGENT_PRIMARY_MODELS` in `agent/llm.py`; override one with `AGENT_MODEL_<NAME>`, for example
  `AGENT_MODEL_SWOT=groq/openai/gpt-oss-20b`). Before this, six agents all started on Qwen, which
  allows about one call a minute, so five of them waited on rate-limit errors first. The split
  was reasoned from each agent's tokens and when it runs, and only partly checked live because the
  free quotas were exhausted. The fallback chain still applies after the first model:

  | Agent | Starts on | Why |
  |---|---|---|
  | Market | Groq `qwen3.8-27b` | best quality for the first, biggest step |
  | Assumption tracker | Groq `qwen3.8-27b` | runs about a minute after market, so the 1,000-token-per-minute bucket has recovered |
  | Competitor discovery, MVP, grounding verifier | Groq `gpt-oss-20b` | 8,000 tokens/min, 200k/day |
  | SWOT, go-to-market | Groq `gpt-oss-120b` | its own 8,000 tokens/min bucket |
  | Revenue models | Gemini 3.8 flash | one call per run, and its own bucket |
  | Advisor | Gemini 3.6 flash | one call per chat message |
- **Provider limits that shape this:** Qwen has a hard 1,000 output-tokens-per-minute cap, so
  its calls stay under about 950 tokens; the `gpt-oss` models allow 8,000 tokens per minute
  plus a daily cap; Gemini's free tier allows about 20 requests a day per model.
- **`reasoning_effort`** has a confirmed-valid value per model (`_REASONING_EFFORT`).
  Qwen accepts `"none"`, the `gpt-oss` models need `"low"`, and `gemini-3.8-flash` has no
  entry on purpose. Check that map before assuming a quota problem needs more retries.
- **Last resort:** a local Ollama model, used only where one is running, then one cloud retry
  after a cooldown, then the section's deterministic fallback. Where a local model exists but
  no email is on file, `/validate` returns `needsEmailForDeepAnalysis`; the run then goes to
  the background and the report is emailed.
- **Caching:** `main.py` caches identical `/validate` requests for 30 minutes and never caches
  a response that has any `errors`, so a cached result is never a hidden failure.

## Local setup

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # required by competitor discovery
cp .env.example .env                      # set GROQ_API_KEY; TAVILY_API_KEY optional
uvicorn main:app --host 127.0.0.1 --port 8000
```

Notes:

- `--reload` restarts the server on every code edit and kills any run in progress, so use it
  only while editing.
- Optional keys enable more: `GEMINI_API_KEY` (fallback models and the advisor),
  `TAVILY_API_KEY` (and `TAVILY_DEEP=0` to skip the deeper, costlier calls),
  `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` (report email), `GOOGLE_OAUTH_CLIENT_ID`
  (Google sign-in), `ADMIN_EMAILS` (admin access), `DATABASE_URL` (Postgres; SQLite is the
  local default). See `.env.example` and [`DEPLOYMENT.md`](../DEPLOYMENT.md).
- Run the tests with `python scripts/run_tests.py` (about 40 seconds, all passing). It runs the suite
  without API keys: `main.py` and `litellm` both load `backend/.env` on import, so a plain
  `python -m unittest discover -s tests` puts your real Groq and Gemini keys into the tests, and any
  test that reaches an LLM step then spends the free quota (about 90 real calls per run were measured).
  CI has no keys, so its plain command is already safe.

## Files

**Entry point and pipeline**
- `main.py`: FastAPI app, CORS, rate limits, request cache, all 21 routes
- `agent/graph.py`: the LangGraph pipeline, state and node wiring
- `agent/chat_graph.py`: the advisor's own small graph (optional scoped search, section routing)

**Retrieval**
- `agent/retrieval.py`: five-angle expansion, product-first competitor queries, App Store layer, dedupe and ranking
- `agent/web_cache.py`: shared cache for search, extract, App Store and company lookups
- `agent/tools.py`: Tavily and DuckDuckGo blend, free fallbacks

**LLM agents**
- `agent/market_agent.py`: market size, TAM/SAM/SOM (sourced, or a labelled estimate), trends, segments
- `agent/competitor_agent.py`: multi-source competitor discovery, enrichment, direct/indirect labels
- `agent/swot_agent.py`, `mvp_agent.py`, `gtm_agent.py`, `assumption_agent.py`, `revenue_agent.py`
- `agent/verification.py`: checks that a cited source supports the claim
- `agent/llm.py`: model chain, `reasoning_effort`, `kickoff_with_fallback()`
- `agent/prompts/`: every prompt, as `<name>_system.md`, `_task.md` and `_output.md`

**Rule-based engines**
- `agent/opportunity_score.py`, `viability_score.py`, `verdict.py`
- `agent/white_space.py`, `strategic_wedge.py`, `voice_of_market.py`
- `agent/contradiction_detector.py`; the two confidence steps (`confidence_node`, `confidence_dashboard_node`) live in `agent/graph.py`
- `agent/experiment_generator.py`, `action_plan.py`, `delivery_roadmap.py`, `commercial_model.py`
- `agent/deterministic_fallback.py`: evidence-based fallbacks when a model call fails

**Output and delivery**
- `agent/report_assembler.py`: the canonical saved report
- `agent/pdf_exporter.py`: ReportLab PDF
- `agent/email_delivery.py`: SendGrid HTTP API email
- `agent/job_store.py`: background validation jobs

**Accounts, storage and telemetry**
- `agent/db.py`, `session_store.py`, `decision_history.py`
- `agent/auth.py`, `google_auth.py`
- `agent/events.py`, `metrics.py`, `platform_metrics.py`, `user_analytics.py`

**Helpers:** `structured_output.py` (compact context and strict JSON parsing),
`output_guard.py` (strips model reasoning text), `idea_category.py`, `pricing.py`.

`scripts/` holds `latency_token_measurement.py` (re-measure latency and token use),
`measure_verification_impact.py`, `smoke_test.py`, `render_deployment_check.py` and
`copy_database.py`.
