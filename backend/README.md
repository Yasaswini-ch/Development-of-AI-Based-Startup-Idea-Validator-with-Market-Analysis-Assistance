# Backend

FastAPI service exposing `POST /validate`. See [`docs/architecture.md`](../docs/architecture.md)
for the full API contract and data flow.

Agents are built with **CrewAI** and orchestrated by a **LangGraph** state graph
(`agent/graph.py`) with 3 nodes so far: `web_search` (Milestone 1) →
`market_opportunity` → `competitor_discovery` (both Milestone 2). Each later node
consumes the Web Search Agent's real results as context (no re-searching). Future
milestones add more agents the same way, as additional graph nodes.

Search uses Tavily when `TAVILY_API_KEY` is set (real relevance score, reliable
results); otherwise it falls back to free DuckDuckGo/Wikipedia/Hacker News search with
a computed relevance score. Each idea is expanded into 5 search angles (market size &
trends, competitors, industry news, customer demand, how others solve this problem),
academic/research-paper domains are filtered out, and results are deduped + ranked.
Only the reasoning LLM (Groq, by default) requires a key.

The Web Search Agent's LLM-generated summary passes a quality gate before being
trusted — if it contains a line break, markdown formatting, or signs of a leaked
reasoning trace (e.g. stray `<think>` tags, "Thought:"/"Final Answer" scaffolding),
it's replaced with a clean fallback sentence built from the real results instead. The
Market Opportunity and Competitor Discovery agents use a different, stronger check
since their output is JSON: a valid, correctly-shaped JSON object recovered from the
raw text (even if surrounded by a rambling scratchpad) is trusted regardless of what's
around it; otherwise it falls back to a safe default.

## Local setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in GROQ_API_KEY (and TAVILY_API_KEY if you have one)
uvicorn main:app --reload --port 8000
```

## Files

- `main.py` — FastAPI app, CORS config, `/validate` route (invokes the LangGraph pipeline)
- `agent/graph.py` — LangGraph `StateGraph`: pipeline state + node wiring
- `agent/crew_agents.py` — Web Search Agent (Milestone 1)
- `agent/market_agent.py` — Market Opportunity & Customer Segmentation Agent
  (Milestone 2) — market size/trends + per-segment pain points/motivations/buying
  behavior
- `agent/competitor_agent.py` — Competitor Discovery & Comparison Agent (Milestone 2)
  — competitors with offering/url/gap/estimated price/feature breadth
- `agent/output_guard.py` — shared reasoning-leak detection used by the Web Search
  Agent's quality gate
- `agent/retrieval.py` — expands one idea into 5 search angles, filters out academic
  sources, dedupes, and ranks results across all of them
- `agent/tools.py` — Tavily search (primary) with a DuckDuckGo/Wikipedia/Hacker News
  fallback chain
- `agent/llm.py` — reasoning LLM provider/model selection (Groq by default)
