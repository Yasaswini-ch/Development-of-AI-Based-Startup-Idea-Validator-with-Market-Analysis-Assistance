# Backend

FastAPI service exposing `POST /validate`. See [`docs/architecture.md`](../docs/architecture.md)
for the full API contract and data flow.

Agents are orchestrated by a **LangGraph** state graph (`agent/graph.py`) with 4 nodes
so far: `web_search` (Milestone 1) → `market_opportunity` → `competitor_discovery` →
`opportunity_score` (all Milestone 2). Each later node consumes the Web Search step's
real results as context (no re-searching). Future milestones add more agents the same
way, as additional graph nodes.

Only `market_opportunity` is a **CrewAI** agent backed by an LLM call. `web_search`
builds its summary from a plain template over the retrieved results instead (see
below) - it used to be a CrewAI agent too, but that call was cut entirely since a
fallback template was already producing the real output often enough to make the LLM
call redundant. `competitor_discovery` was a CrewAI agent through Milestone 2's first
pass, then rewritten to a **local NER step** (spaCy `en_core_web_sm`, no LLM call at
all) — a deliberate decision, not a fallback: every LLM call on the shared Groq key is
a call `market_opportunity` might need instead, and identifying which capitalized
phrases in real search snippets are company names doesn't need an LLM's open-ended
reasoning, just reliable name-reading, which NER does at zero API cost and zero rate
limit. The trade: `gap` is an honest generic disclosure rather than a genuine
comparative judgment, and `estimatedPrice`/`featureBreadth` are always `"unknown"` -
the frontend already hides those badges and the positioning grid when nothing is
classified. See `agent/competitor_agent.py`'s module docstring for the full rationale
and how a scraped snippet's embedded newlines are normalized before NER to avoid
comparison-table pages producing garbled entity names.

`market_opportunity` catches its own failure: if its LLM call fails (after exhausting
the model fallback chain — see below), `marketOpportunity` comes back `null` with a
message in `errors.marketOpportunity` instead of crashing the whole request.
`competitor_discovery` has no LLM call to fail this way, so `competitors` is null only
on an unexpected exception - an empty `competitors: []` is a normal, valid "none
found" outcome, not a failure. Only a failure in `web_search` itself (nothing to
reason over) fails the whole request with a `502`.

Search uses Tavily when `TAVILY_API_KEY` is set (real relevance score, reliable
results); otherwise it falls back to free DuckDuckGo/Wikipedia/Hacker News search with
a computed relevance score. Each idea is expanded into 5 search angles (market size &
trends, competitors, industry news, customer demand, how others solve this problem),
academic/research-paper domains are filtered out, and results are deduped + ranked.
Only the reasoning LLM (Groq, by default) requires a key.

The Market Opportunity agent validates its JSON shape before trusting it: a valid,
correctly-shaped JSON object recovered from the raw text (even if surrounded by a
rambling scratchpad, past `strip_reasoning()`) is trusted regardless of what's around
it; otherwise the node fails and reports through `errors.marketOpportunity`. Neither
the Web Search summary nor Competitor Discovery has an equivalent gate to worry about
anymore, since neither is LLM-generated.

Groq is the only reasoning LLM *provider* wired in — a same-request switch to Gemini
(using the key already in `.env`) was tested directly and dropped: it hangs for minutes
past its own `timeout` parameter instead of failing fast. Instead, `agent/llm.py`'s
`kickoff_with_fallback()` chains through two more *models* on the same Groq account
(`openai/gpt-oss-20b`, then `openai/gpt-oss-120b`, alongside the primary
`qwen/qwen3.6-27b`): Groq rate-limits per model, not per account, so on a rate limit it
switches to the next model immediately (no wait) instead of retrying the same exhausted
one. Only once every model in the chain has been rate limited does it wait out the last
one's suggested cooldown (capped at 30s) for one final try. Each model also has its own
confirmed-working `reasoning_effort` value (`llm.py`'s `_REASONING_EFFORT` map) - by
default `qwen3.6-27b` reserves an output-token budget for hidden `<think>` reasoning
that alone exceeded Groq's ~1000 output-tokens-per-minute cap, the actual cause of most
"Request too large" failures; `reasoning_effort="none"` (or `"low"` for the gpt-oss
fallbacks, which reject `"none"`) eliminates that wasted scratchpad, confirmed directly
against the live API - fewer real failures and far fewer tokens used per call.

Two more quota-pressure mitigations sit on top of this: `main.py` caches identical
`/validate` requests in memory for 30 minutes (never caching a response that has any
`errors` set, so a retry after a transient failure isn't stuck replaying it), and the
frontend disables the submit button for 5 seconds after a submission to cut down on
accidental duplicate requests.

## Local setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in GROQ_API_KEY (and TAVILY_API_KEY if you have one)
uvicorn main:app --reload --port 8000
```

## Files

- `main.py` — FastAPI app, CORS config, `/validate` route (invokes the LangGraph
  pipeline, with an in-memory cache for identical requests)
- `agent/graph.py` — LangGraph `StateGraph`: pipeline state + node wiring; also builds
  the Web Search summary from a plain template (`_build_summary`) - no LLM call
- `agent/market_agent.py` — Market Opportunity & Customer Segmentation Agent
  (Milestone 2) — market size/trends + per-segment pain points/motivations/buying
  behavior. The only remaining LLM-backed agent.
- `agent/competitor_agent.py` — Competitor Discovery (Milestone 2) — competitors with
  offering/url/gap/estimated price/feature breadth, identified via **local spaCy NER
  over the search results, no LLM call**
- `agent/opportunity_score.py` — Opportunity Score post-processing node (Milestone 2
  stretch) — combines the two agents' output into a 0–100 score, with a raw
  search-signal fallback if both upstream agents failed
- `agent/output_guard.py` — `strip_reasoning()`, used by the Market Opportunity agent
  before its own JSON-shape validation
- `agent/retrieval.py` — expands one idea into 5 search angles, filters out academic
  sources, dedupes, and ranks results across all of them
- `agent/tools.py` — Tavily search (primary) with a DuckDuckGo/Wikipedia/Hacker News
  fallback chain
- `agent/llm.py` — reasoning LLM model selection (Groq, incl. per-model
  `reasoning_effort`) and `kickoff_with_fallback()`, which chains through the fallback
  models immediately on a rate limit rather than retrying the same exhausted one
