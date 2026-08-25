# System Architecture — Milestone 1

Owner: Yasaswini · Status: draft (Aug 25, 2026)

## 1. System Overview

The system has three pieces:

1. **Frontend** — React + Tailwind app. Renders the idea submission form and displays
   validation results.
2. **Backend API** — a small FastAPI service exposing `POST /validate`. Receives the
   submitted idea, calls the search agent, and returns a shaped response.
3. **Web Search Agent** — a Python module (used by the backend) that queries the Tavily
   API for market/competitor information related to the submitted idea.

Flow at a glance:

```
User → Frontend (React) → Backend API (FastAPI) → Search Agent → Tavily API
                                                          ↓
User ← Frontend (renders results) ← Backend API ← shaped response
```

The frontend never talks to Tavily directly — it only ever calls our own backend. This
keeps the Tavily API key server-side only and gives us one place to shape/validate
responses before they reach the UI.

## 2. Agent Breakdown

Agents are built with **CrewAI** and orchestrated by a **LangGraph** `StateGraph`. Each
pipeline stage is one LangGraph node wrapping one CrewAI crew (agent + task + tools).
This is deliberate even though Milestone 1 only has one agent: it means Milestone 2-4
agents are added as new graph nodes without restructuring the backend.

**Milestone 1 has a single agent: the Web Search Agent.**

- **Input**: `{ idea, targetCustomer, problem }` from the submitted form
- **CrewAI role**: "Web Search Agent" — goal: retrieve live, relevant market/competitor
  data; tool: Tavily search
- **LangGraph node**: `web_search` — runs the crew, parses its structured
  (`output_pydantic`) result into pipeline state
- **Output**: `{ summary, results[] }` where `results` is `{ title, snippet, url }[]`,
  produced directly by the CrewAI task's structured output (not text-parsed)

**Future extension point (Milestone 2+):** Market Opportunity, Competitor Discovery,
SWOT/Risk, MVP Recommendation, GTM, and Report Generation agents each become a new
CrewAI crew wrapped in a new LangGraph node (e.g. `market_opportunity`,
`competitor_discovery`, ...), wired into the same graph with `add_edge`. LangGraph's
state dict carries each stage's output forward so later agents can consume earlier
agents' results (context passing), and partial failures are handled per-node rather
than crashing the whole pipeline.

## 3. Data Flow

1. User fills in idea / target customer / problem and submits the form
2. Frontend sends `POST /validate` with the form data
3. Backend validates input (idea field required, non-empty)
   - If invalid → return `400` with `{ error: "..." }`, frontend shows inline field error
4. Backend calls the Search Agent, which builds a Tavily query and calls the Tavily API
   - If Tavily times out / rate-limits / errors → backend returns `502` with
     `{ error: "..." }`, frontend shows an `ErrorState` ("couldn't fetch results, try
     again")
   - If Tavily returns zero results → backend returns `200` with `{ summary: "...",
     results: [] }`, frontend shows an `EmptyState` ("no market data found for this
     idea")
5. Backend shapes the response into the shared contract and returns `200`
6. Frontend renders the summary + result cards below the form

## 4. API Contract

```
POST /validate
Content-Type: application/json

Request:
{
  "idea": string,            // required, non-empty
  "targetCustomer": string,  // optional
  "problem": string          // optional
}

Response 200:
{
  "summary": string,
  "results": [
    { "title": string, "snippet": string, "url": string }
  ]
}

Response 400 / 502:
{
  "error": string
}
```

This contract is locked for Milestone 1 — Varshini (agent) and Anu Kumari (frontend)
should build against this without needing to sync on every field.

## 5. Tech Stack Decisions

| Layer | Choice | Why |
|---|---|---|
| Frontend | React (Vite) + Tailwind CSS | Team wants a premium, polished UI — faster to achieve with component reuse + utility classes than hand-rolled CSS. **Note:** this deviates from the milestone guide's plain HTML/CSS/JS wording; flagging that explicitly since it's a deliberate call. |
| Backend | FastAPI | Lightweight, async-friendly, minimal boilerplate for a single endpoint, easy to extend with more agents later. |
| Orchestration | LangGraph | Owns pipeline state and node wiring — each agent is a graph node, so M2-M4 agents are added without restructuring the backend. |
| Agents | CrewAI | Role/goal/tool-based agent definitions, one Agent+Task per pipeline stage — matches the brief's named-agent structure directly. |
| Search | Tavily API | Specified by the milestone guide; exposed to the Web Search Agent as a CrewAI tool. |
| Reasoning LLM | OpenAI (via CrewAI/LiteLLM) | Default provider for agent reasoning; configurable via `OPENAI_API_KEY`. |
| Hosting | Render | Already set up for this repo (see `render.yaml`). |

## 6. Deployment Topology

Two Render web services:

- **`startup-validator-frontend`** — serves the built React app (static site or Node
  web service)
- **`startup-validator-backend`** — runs the FastAPI service; holds the `TAVILY_API_KEY`
  as a Render environment variable (never committed to the repo)

Frontend reads the backend's URL via `VITE_API_URL` (env var, set per environment —
local vs. deployed).

## 7. Error Handling Policy

- Backend never lets a raw exception/stack trace reach the frontend — every failure path
  returns `{ error: string }` with an appropriate status code
- Frontend never shows a blank or frozen screen on failure — every failed/empty state
  renders a specific `ErrorState` or `EmptyState` component with a human-readable message
- Timeouts: backend enforces a reasonable timeout on the Tavily call (e.g. 10s) so a slow
  external API doesn't hang the whole request

## 8. Repo Structure (proposed)

```
.
├── frontend/          # React + Tailwind app (Anu Kumari)
│   └── ...
├── backend/           # FastAPI app + search agent (Varshini)
│   ├── main.py         # POST /validate route
│   └── agent/
│       └── search_agent.py
├── docs/
│   ├── architecture.md        # this file
│   ├── milestone1-plan.md
│   └── frontend-spec.md
├── render.yaml         # updated for two services (Yalene)
└── README.md
```

The existing root-level `app.py` (Streamlit prototype) stays as-is for reference but is
superseded by `frontend/` + `backend/` going forward.
