# Backend

FastAPI service exposing `POST /validate`. See [`docs/architecture.md`](../docs/architecture.md)
for the full API contract and data flow.

## Local setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill in TAVILY_API_KEY
uvicorn main:app --reload --port 8000
```

## Files

- `main.py` — FastAPI app, CORS config, `/validate` route
- `agent/search_agent.py` — builds a Tavily query from the submitted idea and shapes
  the response into `{ summary, results }`
