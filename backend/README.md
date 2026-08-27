# Backend

FastAPI service exposing `POST /validate`. See [`docs/architecture.md`](../docs/architecture.md)
for the full API contract and data flow.

Agents are built with **CrewAI** (role/goal/tools per agent) and orchestrated by a
**LangGraph** state graph (`agent/graph.py`). Milestone 1 has one node — the Web Search
Agent — future milestones add more agents as additional graph nodes, each wrapping
their own CrewAI crew.

Search uses Tavily when `TAVILY_API_KEY` is set (real relevance score, reliable
results); otherwise it falls back to free DuckDuckGo/Wikipedia/Hacker News search with
a computed relevance score. Each idea is expanded into 5 search angles (market size &
trends, competitors, industry news, customer demand, how others solve this problem),
academic/research-paper domains are filtered out, and results are deduped + ranked.
Only the reasoning LLM (Groq, by default) requires a key.

The LLM-generated summary passes a quality gate before being trusted — if it's too long
or contains signs of a leaked reasoning trace (e.g. stray `<think>` tags, "Thought:"/
"Final Answer" scaffolding), it's replaced with a clean fallback sentence built from the
real results instead.

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
- `agent/crew_agents.py` — CrewAI `Agent`/`Task`/`Crew` definitions (one per pipeline stage)
- `agent/retrieval.py` — expands one idea into 5 search angles, filters out academic
  sources, dedupes, and ranks results across all of them
- `agent/tools.py` — Tavily search (primary) with a DuckDuckGo/Wikipedia/Hacker News
  fallback chain, plus a CrewAI tool wrapper
- `agent/llm.py` — reasoning LLM provider/model selection (Groq by default)
