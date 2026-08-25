# Backend

FastAPI service exposing `POST /validate`. See [`docs/architecture.md`](../docs/architecture.md)
for the full API contract and data flow.

Agents are built with **CrewAI** (role/goal/tools per agent) and orchestrated by a
**LangGraph** state graph (`agent/graph.py`). Milestone 1 has one node — the Web Search
Agent — future milestones add more agents as additional graph nodes, each wrapping
their own CrewAI crew.

## Local setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in TAVILY_API_KEY and OPENAI_API_KEY
uvicorn main:app --reload --port 8000
```

## Files

- `main.py` — FastAPI app, CORS config, `/validate` route (invokes the LangGraph pipeline)
- `agent/graph.py` — LangGraph `StateGraph`: pipeline state + node wiring
- `agent/crew_agents.py` — CrewAI `Agent`/`Task`/`Crew` definitions (one per pipeline stage)
- `agent/tools.py` — CrewAI tools (Tavily web search)
- `agent/schemas.py` — Pydantic output schemas shared between CrewAI tasks and the API contract
