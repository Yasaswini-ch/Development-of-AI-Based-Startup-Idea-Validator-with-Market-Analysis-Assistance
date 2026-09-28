# Scaling Options: What We Can Test and What We Can Change

**Version:** 1.0 · 2026-09-28 (written against the `staging` branch)  
**Status:** reference only. Nothing here is implemented yet.  
**Related:** [load-testing-plan.md](load-testing-plan.md), [09 Cloud Deployment](09_AFFINITY_CLOUD_DEPLOYMENT_AND_DEVOPS_RUNBOOKS.md), [known-limitations-and-future-work.md](known-limitations-and-future-work.md)

Affinity's limiting resource is unusual for a web app: it is not HTTP throughput, it is
**shared LLM quota and the minutes each validation takes**. So "scaling" here means
several different things. This doc lists each type, what the 5–6 user load test can
tell us about it, and the options for improving it, cheapest first.

---

## 1. Where the system stands today

| Layer | Today | Relevant setting |
|---|---|---|
| Web service | 1 Render **free** instance (512 MB, 0.1 CPU, sleeps after 15 min idle), one `uvicorn` process | `render.yaml` |
| Pipeline execution | runs in a thread inside the web process (`asyncio.to_thread`), ~20 LangGraph nodes, ~8–10 LLM calls | `main.py` `/validate`, `graph.py` |
| LLM | one Groq key + one Gemini key shared by all users; 5-model fallback chain; max 4 concurrent calls per process | `llm.py` |
| Search | Tavily (1,000 free credits/month), free DDG/Wikipedia/HN fallback | `tools.py` |
| Database | Render free Postgres (expires after 30 days), pool of 5 per process | `db.py` |
| Cache | Postgres table, 30-minute TTL, exact-match on the request | `main.py` `_cache_key` |
| Rate limiting | in-memory, per IP, per process | `main.py` |
| Frontend | static Vite build on Render | `frontend/` |

## 2. Types of scaling, and what the load test can check

| # | Type | Question it answers | Can 5–6 users test it? |
|---|---|---|---|
| 1 | **Concurrency (load) scaling** | Do N simultaneous validations all succeed, and how does latency grow with N? | **Yes, directly.** This is the main load test. |
| 2 | **Vertical scaling** (bigger instance) | Does more RAM/CPU on one instance fix the bottleneck? | Yes: repeat the burst scenario on a Starter/Standard instance and compare. |
| 3 | **Horizontal scaling** (more instances) | Does a second web instance double capacity? | Partly. It helps CPU/RAM, **not** LLM quota. It also exposes state that lives in one process (rate limits, metrics counters). |
| 4 | **External-quota scaling** (LLM + search) | How many runs per minute/day before providers throttle us? | **Yes, and it's the most likely limit.** Count fallback-model calls and 429s from providers. |
| 5 | **Database scaling** | Do connections, storage and query time hold up? | Only lightly; 6 users won't stress Postgres. The pool-timeout log line is the signal. |
| 6 | **Data / storage scaling** | What happens as sessions, events and cache rows grow? | No; needs a soak test or projection. Storage is capped by TTLs today (7-day sessions, 200 rows). |
| 7 | **Latency scaling** (time per request) | Can one validation get faster, independent of load? | Yes, via the single-user baseline (S0). |
| 8 | **Cost scaling** | What does each extra user cost once free tiers run out? | Yes: tokens per run × provider price, from the `llm_call` logs. |
| 9 | **Resilience / graceful degradation** | When a limit is hit, does the app degrade cleanly? | Yes: the burst scenario should show fallbacks and `degraded` sections, not 500s. |
| 10 | **Cold-start / availability** | How long does the first request after idle take? | Yes: one request after 15+ minutes idle. |

## 3. Options per scaling type

Each option lists rough cost and effort. Prices are indicative; check the provider's
current pricing page before deciding.

### 3.1 Vertical: a bigger Render instance
- **What:** move the web service from Free to Starter (~$7/month, no sleep) or
  Standard (~$25/month, 2 GB RAM, 1 CPU).
- **Fixes:** cold starts, out-of-memory risk, slow spaCy/PDF work.
- **Doesn't fix:** LLM quota.
- **Effort:** a setting change. **Recommended first** if the load test shows memory
  pressure or cold starts matter for a demo.

### 3.2 Horizontal: more instances or workers
- **What:** 2+ Render instances behind Render's load balancer, or `uvicorn --workers 2`.
- **Needs first:** rate limits and in-process metrics moved out of process memory
  (Postgres or Redis), otherwise each instance counts separately. Sessions, jobs and
  cache are already in Postgres, so they work across instances today.
- **Watch:** instances × `DB_POOL_SIZE` must stay under the database's connection limit;
  `MAX_CONCURRENT_LLM_CALLS` is per process, so total LLM concurrency multiplies too.
- **Effort:** medium.

### 3.3 Job queue: take the pipeline out of the web request
- **What:** `/validate` enqueues a job and returns a job id immediately; separate worker
  processes (Render Background Worker with Celery/RQ/Arq on Redis, or a Postgres-backed
  queue) run pipelines; the frontend polls `/validate/status/{job_id}` (which already
  exists for the email path).
- **Fixes:** the web process stays responsive regardless of how many pipelines run;
  workers scale independently; a crash loses one job, not the web server.
- **Effort:** medium to high. The biggest architectural win once there are more than a
  handful of concurrent users.

### 3.4 LLM quota scaling (the real ceiling)
Options, from cheapest:
1. **Cut tokens per run**: tighten `compact_sources` and `max_tokens`, skip LLM steps in
   `quick` mode, merge small calls. Measure with `latency_token_measurement.py`.
2. **Smarter caching**: cache per-node outputs keyed by normalised idea + sources, so a
   re-run with a tweaked description reuses search and market analysis.
3. **Per-user quotas**: e.g. N deep validations per user per day, so one user can't drain
   the shared key.
4. **Paid tier on one provider**: Groq's or Gemini's paid tiers raise per-minute limits by
   orders of magnitude. At roughly 10–25k tokens per run, paid cost is on the order of
   cents per validation (confirm with the load-test token numbers).
5. **More providers in the chain** (e.g. a paid Claude or OpenAI model as the last cloud
   tier before the deterministic fallback).
6. **Self-hosted model on a GPU** for the existing Ollama tier (see Known Limitations §3.1).

### 3.5 Search quota scaling
- Cache search results per query for longer than 30 minutes (market facts don't change
  hourly).
- Tavily's paid plan or the student plan once 1,000 credits/month isn't enough.
- Keep the free fallback chain as the safety net; it already exists.

### 3.6 Database scaling
- Paid Postgres plan (also removes the 30-day expiry, the bigger risk today).
- Add Alembic before more schema changes (Known Limitations §1.3).
- Indexes on `user_id` / `updated_at` for History and Dashboard queries if they slow down.
- PgBouncer or a lower per-process pool if many instances are added.

### 3.7 Frontend / static assets
Already a static build; a CDN (Render's static sites are CDN-backed) handles far more
than we need. No action.

### 3.8 Observability needed to scale safely
- Persist API/node success counters in the event log (today they reset on restart).
- Record tokens and cost per run and per model (the Platform Health tokens/cost graphs
  request covers this).
- Alert on fallback-model share and on `degraded` runs.

## 4. Suggested order

1. Run the load test as planned ([load-testing-plan.md](load-testing-plan.md)) on the
   current free setup, to get baseline numbers.
2. If memory or cold starts fail: **vertical** (3.1).
3. If LLM fallbacks or `degraded` runs appear: **token reduction + per-user quotas**
   (3.4.1–3.4.3), then a **paid LLM tier** (3.4.4).
4. Before any demo or real users: **paid Postgres** (3.6).
5. Only if we expect well beyond ~10 concurrent users: **job queue + horizontal**
   (3.3, 3.2).

## 5. How to present this in a review

"We tested concurrency scaling at 5–6 users and measured where it degrades. The
bottleneck is shared LLM quota, not server capacity, so adding servers alone doesn't
help. The next steps are, in order: a bigger instance, token reduction and per-user
quotas, a paid LLM tier, and a job queue with separate workers if usage grows further."
