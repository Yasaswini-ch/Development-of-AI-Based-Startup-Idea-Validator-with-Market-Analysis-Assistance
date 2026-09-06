# Backend

FastAPI service exposing `POST /validate`. See [`docs/architecture.md`](../docs/architecture.md)
for the full API contract and data flow.

Agents are built with **CrewAI** and orchestrated by a **LangGraph** state graph
(`agent/graph.py`) with 4 nodes so far: `web_search` (Milestone 1) →
`market_opportunity` → `competitor_discovery` → `opportunity_score` (all Milestone 2).
Each later node consumes the Web Search step's real results as context (no
re-searching). Future milestones add more agents the same way, as additional graph
nodes.

Only `market_opportunity` and `competitor_discovery` are CrewAI agents backed by an LLM
call. `web_search` builds its summary from a plain template over the retrieved results
instead (see below) - it used to be a third CrewAI agent, but that call was cut
entirely since a fallback template was already producing the real output often enough
to make the LLM call redundant.

`market_opportunity` and `competitor_discovery` each catch their own failures: if one's
LLM call fails (after exhausting the model fallback chain — see below), that section of the response
comes back `null` with a message in `errors.<node>` instead of crashing the whole
request. Only a failure in `web_search` itself (nothing to reason over) fails the whole
request with a `502`.

Search uses Tavily when `TAVILY_API_KEY` is set (real relevance score, reliable
results); otherwise it falls back to free DuckDuckGo/Wikipedia/Hacker News search with
a computed relevance score. Each idea is expanded into 5 search angles (market size &
trends, competitors, industry news, customer demand, how others solve this problem),
academic/research-paper domains are filtered out, and results are deduped + ranked.
Only the reasoning LLM (Groq, by default) requires a key.

The Market Opportunity and Competitor Discovery agents validate their JSON shape
before trusting it: a valid, correctly-shaped JSON object recovered from the raw text
(even if surrounded by a rambling scratchpad, past `strip_reasoning()`) is trusted
regardless of what's around it; otherwise the node fails and reports through
`errors.<node>`. The Web Search summary has no equivalent gate to worry about anymore
since it isn't LLM-generated.

Groq is the only reasoning LLM *provider* wired in — a same-request switch to Gemini
(using the key already in `.env`) was tested directly and dropped: it hangs for minutes
past its own `timeout` parameter instead of failing fast. Instead, `agent/llm.py`'s
`kickoff_with_fallback()` chains through two more *models* on the same Groq account
(`openai/gpt-oss-20b`, then `openai/gpt-oss-120b`, alongside the primary
`qwen/qwen3.6-27b`): Groq rate-limits per model, not per account, so on a rate limit it
switches to the next model immediately (no wait) instead of retrying the same exhausted
one. Only once every model in the chain has been rate limited does it wait out the last
one's suggested cooldown (capped at 30s) for one final try.

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
  behavior
- `agent/competitor_agent.py` — Competitor Discovery & Comparison Agent (Milestone 2)
  — competitors with offering/url/gap/estimated price/feature breadth
- `agent/opportunity_score.py` — Opportunity Score post-processing node (Milestone 2
  stretch) — combines the two agents' output into a 0–100 score, with a raw
  search-signal fallback if both upstream agents failed
- `agent/output_guard.py` — `strip_reasoning()`, used by the Market Opportunity and
  Competitor Discovery agents before their own JSON-shape validation
- `agent/retrieval.py` — expands one idea into 5 search angles, filters out academic
  sources, dedupes, and ranks results across all of them
- `agent/tools.py` — Tavily search (primary) with a DuckDuckGo/Wikipedia/Hacker News
  fallback chain
- `agent/llm.py` — reasoning LLM model selection (Groq) and `kickoff_with_fallback()`,
  which chains through the fallback models immediately on a rate limit rather than
  retrying the same exhausted one
