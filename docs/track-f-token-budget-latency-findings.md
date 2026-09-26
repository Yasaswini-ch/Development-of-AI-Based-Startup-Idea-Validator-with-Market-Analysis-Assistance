# Track F — Token-Budget & Latency Pass: Findings

**Status: instrumentation and tooling complete; real measurement not yet run.**

This pass's own task (per the Milestone 4 task division) is to run real sample
ideas through the pipeline, measure actual latency/token numbers, and tune
`max_tokens` / `compact_sources` limits from that data. No environment with a
working `GROQ_API_KEY` was available while this document was written, so the
"tune from actual numbers" step has **not** happened yet — this document
covers what a structural review of the existing code can responsibly say
without live data, and hands off exactly what's needed to finish the job.

## 1. Instrumentation — already complete

Two log lines already carry everything this pass needs, added in earlier
Milestone 4 work (`graph.py`'s `_timed` wrapper, `llm.py`'s
`_kickoff_with_metrics`):

```
[market_opportunity] elapsed_ms=842
llm_call model=groq/qwen/qwen3.8-27b elapsed_ms=780 prompt_tokens=612 completion_tokens=298 total_tokens=910
```

Nothing needed adding here — the gap was collection and analysis, not
instrumentation.

## 2. New tooling

- **`backend/scripts/latency_token_measurement.py`** — runs N real sample
  ideas through `agent.graph.pipeline`, captures the log lines above, and
  prints per-node and per-model latency/token stats plus deterministic-
  fallback counts. Verified structurally (log-parsing regexes confirmed
  against real log output from a mocked `crewai.Crew.kickoff`) but never run
  against a real model, since no API key was available. Run it with:

  ```bash
  cd backend
  export GROQ_API_KEY=...      # required
  export TAVILY_API_KEY=...    # optional - falls back to free search providers
  python scripts/latency_token_measurement.py --ideas 5
  ```

- **`backend/scripts/render_deployment_check.py`** (from the earlier part of
  this pass) — separately useful here too: its `--full` flag runs one real
  `/validate` request against the *deployed* Render backend, which already
  has real keys configured, and would surface the same log lines server-side.

## 3. Current configured budgets (from reading the code, not measurement)

| Agent | `max_tokens` | `compact_sources` limit | Last tuning note |
|---|---|---|---|
| `market_agent.py` | 750 | up to 10 (`MAX_SOURCES_IN_CONTEXT`) | "confirmed live to truncate into invalid JSON at 550" |
| `swot_agent.py` | 750 | 6 (library default) | "confirmed live to truncate at 550" |
| `gtm_agent.py` | 450 | 6 (library default) | "confirmed live to truncate JSON output itself" at 250 |
| `mvp_agent.py` | 450 | 6 (library default) | "confirmed live to truncate JSON output itself" at 250 |
| `chat_graph.py` (advisor) | 550 | n/a | not documented |

All four numbers above were empirically tuned at some point (the commit
history has "Rebalanced to N (was X, briefly tried Y)" notes for each) — this
pass didn't have to guess these from nothing, it's re-verifying whether they
still hold.

## 4. Two findings worth flagging before more schema fields get added

**4.1 — `market_agent.py`'s schema grew *after* its last confirmed tuning.**
The commit that added TAM/SAM/SOM (three more `{text, sourceIds}` claims on
top of the existing `marketSize`/`trends`/`segments` schema) landed after the
commit containing the "confirmed live to truncate at 550, rebalanced to 750"
note. That commit's own message says it was "verified live against the real
Groq API," which is worth trusting at face value rather than second-guessing
without evidence — but it's one verification run against a schema that's
denser than what 750 was originally tuned for, and LLM output length isn't
perfectly deterministic. **Recommendation:** when `latency_token_measurement.py`
is run for real, look at `market_opportunity`'s `completion_tokens` numbers
specifically against the 750 ceiling before anything else — it's the
agent most likely to be running closest to its limit right now.

**4.2 — `swot_agent.py`/`gtm_agent.py`/`mvp_agent.py` only ever see 6 sources,
`market_agent.py` sees up to 10.** `compact_sources()` defaults to
`limit=6`; three of the four agents call it with no override, while
`market_agent.py` explicitly widens it to `MAX_SOURCES_IN_CONTEXT` (10). This
looks like an unexamined default rather than a deliberate choice — the other
three agents can never cite `src-7`..`src-10` even when those sources exist
and are relevant. **This document deliberately does not change it.** Widening
it is plausible and low-risk on the input side (each agent's own
`compact_json(..., max_chars=...)` call already caps total prompt length
independently), but whether it changes *output* length (e.g. more cited
`sourceIds` per claim) can't be answered without real data, and gtm/mvp's
450-token budget has less headroom than market's 750 to absorb a surprise.
**Recommendation:** the first candidate change to test once real numbers are
available, specifically checking whether `completion_tokens` moves when the
limit changes from 6 to 10.

## 5. Explicitly not done here

- No `max_tokens` or `compact_sources` value was changed. Doing so without
  real data would be exactly the "guessing" this pass exists to replace.
- `docs/api-cost-accuracy-performance-metrics.md` is now significantly stale
  (still describes a "one LLM call per request" Milestone 1/2 pipeline; the
  pipeline now makes five-plus LLM calls per request across SWOT/MVP/GTM/
  market/chat). Refreshing it belongs to Track F item 3 (documentation), not
  this one, but it's the natural place to fold this document's findings into
  once real numbers exist.
