# Load Testing Plan: 5–6 Concurrent Users

**Version:** 1.0 · 2026-09-28 (written against the `staging` branch)  
**Status:** plan only. Run it once feature work is finished, against a deployed build.  
**Related:** [scaling-options.md](scaling-options.md), [track-f-token-budget-latency-findings.md](track-f-token-budget-latency-findings.md), [ops-runbook-troubleshooting.md](ops-runbook-troubleshooting.md)

This doc says what to test, how to run it, what numbers to record, and what we expect
to break first. The goal is not a big number; it is to show that Affinity stays
correct and usable when a small class or incubator cohort (5–6 founders) validates
ideas at the same time, and to know exactly where it degrades.

---

## 1. Questions the test must answer

1. Do 6 simultaneous `/validate` requests all finish with a full report, with no
   section marked `degraded: true`?
2. How long does each take end to end (p50 / p95 / max), compared with a single user?
3. How many LLM calls fall through the fallback chain (Groq → Gemini → deterministic)
   under load, and how many tokens does one run cost?
4. Does the backend stay up (no out-of-memory restart on Render's 512 MB free
   instance), and do the lighter endpoints (`/health`, `/me/history`, report view)
   stay responsive while 6 pipelines run?
5. Do PDF export and the advisor chat still work while validations are running?

## 2. What one validation costs (why 6 users is already a real test)

| Resource per `/validate` | Approximate amount | Where it comes from |
|---|---|---|
| Search calls | 5 angles × 1–2 queries (Tavily, or DDG/Wikipedia/HN fallback) | `retrieval.build_search_angles` |
| LLM calls | ~8–10: market, competitor profile (deep mode), SWOT, MVP, GTM, assumptions, revenue, verification, plus one Gemini price/breadth refinement | `graph.py` nodes, `competitor_agent.py` |
| Tokens | roughly 1–3k per call, so ~10–25k per run (measure it, see §5) | `llm_call ... total_tokens=` log lines |
| Wall time (single user) | typically 1–3 minutes | `node.*` timings in `/metrics` |

Six users at once is therefore ~50–60 LLM calls and ~60–150k tokens inside a few
minutes, all on **one shared Groq key and one shared Gemini key**. That is the load
that matters, not HTTP requests per second.

## 3. Built-in limits that shape the test

Read these before running, or the results will be misleading.

| Mechanism | Setting | Effect on a load test |
|---|---|---|
| Result cache | identical idea text is served from a 30-minute cache (`_CACHE_TTL_SECONDS`) | **Every virtual user must submit a different idea**, or you are testing the cache, not the pipeline. |
| Per-IP rate limit | `VALIDATE_RATE_LIMIT_PER_MINUTE=10`, chat 30, PDF 10 | All virtual users come from one IP. 6 validations fit; a burst of more than 10 per minute gets HTTP 429. Record 429s as "limiter working", not failures. |
| LLM concurrency cap | `MAX_CONCURRENT_LLM_CALLS=4` (a semaphore in `llm.py`) | With 6 pipelines, at most 4 LLM calls run at once; the rest queue. Expect latency to grow, not errors. |
| Email async path | if an email is given and the run passes 60 s (`VALIDATE_ASYNC_THRESHOLD_SECONDS`), the API returns 202 and emails later | Leave `email` empty in the load script so no real emails are sent and every request returns the full result. |
| DB pool | `DB_POOL_SIZE=5`, timeout 10 s | Sessions, jobs and cache all use Postgres. Watch for pool timeouts in logs. |
| Render free web | 512 MB RAM, 0.1 CPU, spins down after 15 minutes idle | Warm the service up with `/health` first, or the first request includes a cold start. |

## 4. Test scenarios

Run each scenario against the same deployment, one after another, with a short
cool-down between them so provider rate-limit windows reset.

| # | Scenario | Users | What it shows |
|---|---|---|---|
| S0 | **Baseline**: one user, 3 different ideas in a row | 1 | Reference latency and token cost per run |
| S1 | **Ramp**: add one user every 30 s up to 6, each submits 1 idea | 1 → 6 | Where latency starts to climb |
| S2 | **Burst**: 6 users submit at the same second | 6 | Worst case for the shared LLM quota and the semaphore |
| S3 | **Mixed realistic**: 6 users; each validates, then opens the report, exports a PDF, asks 2 chat questions, views History | 6 | Whether light endpoints stay fast while pipelines run |
| S4 | **Soak** (optional): 5 users, one validation every 5 minutes each, for 30 minutes | 5 | Memory growth, quota exhaustion over time, DB pool stability |

Use 6–12 genuinely different ideas across domains (software, food, hardware,
fintech, education) so search and competitor results vary.

## 5. How to run it

### 5.1 Tooling

[Locust](https://locust.io) fits: it is Python (same stack as the backend), models
"users" rather than raw requests, and produces p50/p95 charts and a CSV. `k6` is an
equally good alternative. Install it on the tester's machine, not in
`backend/requirements.txt`.

A minimal `locustfile.py` for scenarios S1/S2:

```python
import itertools, uuid
from locust import HttpUser, task, between

IDEAS = itertools.cycle([
    "Meal-prep delivery for night-shift nurses",
    "Invoice tool for freelance video editors",
    "Smart water bottle that tracks kids' hydration",
    "Budgeting app for international students",
    "Marketplace for renting camera gear locally",
    "AI tutor for high-school chemistry practicals",
])

class Founder(HttpUser):
    wait_time = between(5, 15)

    @task
    def validate(self):
        idea = f"{next(IDEAS)} ({uuid.uuid4().hex[:6]})"  # unique text defeats the cache
        with self.client.post(
            "/validate",
            json={"idea": idea, "targetCustomer": "", "problem": "", "mode": "deep"},
            timeout=420,
            catch_response=True,
            name="/validate",
        ) as r:
            if r.status_code == 429:
                r.success()  # rate limiter doing its job; count separately
            elif r.status_code != 200:
                r.failure(f"HTTP {r.status_code}")
            elif any(isinstance(v, dict) and v.get("degraded") for v in r.json().values()):
                r.failure("degraded section")  # a section fell back to the deterministic result
```

Run it headless and keep the CSV:

```bash
locust -f locustfile.py --host https://<backend>.onrender.com \
       --users 6 --spawn-rate 6 --run-time 10m --headless --csv results/s2_burst
```

The body matches `ValidateRequest` in `backend/main.py` as of this version. Add S3's report/PDF/chat/history calls as extra `@task`s.

### 5.2 Where to read the server side

- **`GET /metrics`**: per-node timings, cache hits, API success counters (in-process;
  resets on restart, so read it right after each scenario).
- **Platform Health** (`/admin/platform-metrics`, admin only): node latency and success
  rates from the event log.
- **Render logs**: `llm_call model=... elapsed_ms=... total_tokens=...` lines give model
  used, latency and tokens per call; count fallbacks by model name. Also look for
  `Cloud path exhausted`, `degraded`, pool timeouts and OOM restarts.
- **Render metrics tab**: memory and CPU for the service during each scenario.
- **Groq and Gemini consoles**: requests and tokens used during the window.
- `backend/scripts/latency_token_measurement.py` can produce the single-user S0 numbers
  locally with the same keys.

## 6. Results template

Record one row per scenario in this doc (or a copy of it) when the test is run.

| Scenario | Requests | OK | Degraded | 429 | Errors | p50 (s) | p95 (s) | Max (s) | Peak RAM | LLM calls | % on fallback model | Tokens / run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S0 | | | | | | | | | | | | |
| S1 | | | | | | | | | | | | |
| S2 | | | | | | | | | | | | |
| S3 | | | | | | | | | | | | |
| S4 | | | | | | | | | | | | |

## 7. Pass criteria (proposed)

- **All** S1–S3 validations return 200 with a report; **≤ 1 in 6** is `degraded`.
- S2 p95 end-to-end ≤ 3× the S0 single-user p50.
- No backend restart or OOM during any scenario.
- During S3, `/health` and History respond in under 2 s at p95.
- PDF export succeeds for every finished report.

## 8. Expected bottlenecks (hypotheses to confirm or reject)

In the order we expect them to appear:

1. **Groq free-tier rate limits (tokens and requests per minute).** Six pipelines on one
   key will hit per-minute limits first. The chain in `llm.py` then moves to
   `gpt-oss-20b`, `gpt-oss-120b`, then Gemini. Expect a visible share of calls on
   fallback models in S2, more latency from rate-limit waits, and possibly some
   `degraded` runs if every model is exhausted at once.
2. **The `MAX_CONCURRENT_LLM_CALLS=4` semaphore.** It protects the quota but makes
   later pipelines wait. S2 latency should climb roughly in steps of 4.
3. **Memory on the 512 MB instance.** spaCy's model, CrewAI/LangChain, six in-flight
   pipelines' search results and a PDF render at the same time may push memory near the
   limit. An OOM shows as a restart in Render's events.
4. **CPU at 0.1 vCPU.** spaCy NER and PDF generation are CPU work; with six of them the
   event loop can feel slow even when nothing fails. Watch S3's `/health` latency.
5. **Tavily credits.** ~5–10 searches per run; a full test day uses roughly 100–300
   credits of the 1,000 free monthly credits. Budget for it or accept the free fallback
   (which changes result quality and relevance scores).
6. **DB pool** is unlikely to be the first thing to break at this size, but pool
   timeouts in the logs would show it.

## 9. Safety checklist before running

- Tell the team; the test spends shared LLM and Tavily quota for everyone.
- Run against a deployment you can restart, ideally a staging service, not during a demo.
- Leave `email` empty so SendGrid sends nothing.
- Warm the service with `/health` first.
- Don't raise the rate limits on the production service; if a test needs more than 10
  validations per minute from one IP, raise `VALIDATE_RATE_LIMIT_PER_MINUTE` on a
  staging service only.
