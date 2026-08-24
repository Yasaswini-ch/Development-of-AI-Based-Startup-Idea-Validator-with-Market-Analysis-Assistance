# Milestone 1 — Team Plan

Aug 25 – Aug 28, 2026 (compressed, deadline-driven) · Goal: working idea-submission
interface + live Tavily web search agent, with the full system architecture documented.

## Task Division (4 people)

### 1. System Architecture — Yasaswini
- Own the overall design: how the frontend, backend/search agent, and data flow fit together
- Decide and document the frontend↔backend API contract (see below)
- Write `docs/architecture.md`: agents, data flow diagram, structure, tech stack decisions

**Detailed scope for `docs/architecture.md`:**
- **System overview** — one paragraph + diagram showing the three pieces: React/Tailwind
  frontend, backend API service, Tavily-backed search agent — and how a request moves
  through them
- **Agent breakdown** — for Milestone 1 there's one agent (the web search agent); define
  its responsibility precisely: takes `{ idea, targetCustomer, problem }`, builds a
  Tavily query, returns `{ summary, results[] }`. Note where future agents (e.g. a
  scoring/analysis agent, a competitor-comparison agent) would plug into the same flow
  so Milestone 2+ has a clear extension point
- **Data flow diagram** — step-by-step: user submits form → frontend POSTs to
  `/validate` → backend validates input → backend calls Tavily API → backend shapes
  response → frontend renders results. Call out failure branches (Tavily timeout/error,
  empty idea, no results found) and what the user sees at each
- **API contract** — finalize the request/response shape below (field names, types,
  required vs optional) so Varshini and Anu Kumari can build against it independently
  without waiting on each other
- **Tech stack decisions** — record *why*, not just what: React + Tailwind for the
  frontend (premium UI, deviates from the milestone guide's plain HTML/CSS/JS — note
  this explicitly), FastAPI/Flask for the backend (pick one and justify), Tavily for
  search
- **Deployment topology** — how this maps onto Render: is it one service or two
  (frontend + backend)? Where do env vars (Tavily key) live? This feeds directly into
  Yalene's task 4, so be concrete
- **Error/edge-case handling policy** — a short section defining what "graceful
  failure" means system-wide (e.g. always return JSON with an `error` field, never a
  raw 500/stack trace to the frontend) so Varshini and Anu Kumari implement it
  consistently on both ends
- **Repo structure** — proposed folder layout (`frontend/`, `backend/` or `agent/`,
  `docs/`) so everyone commits into the right place from day one

### 2. Web Search Agent (Tavily integration) — Varshini
- Sign up for a Tavily API key and store it via `.env` (never commit it — add `.env` to
  `.gitignore`)
- Set up a Python module (e.g. `agent/search_agent.py`) with a function like
  `search_market(idea: str, target_customer: str, problem: str) -> dict`
- Call the Tavily API with a query built from the submitted idea/problem/target customer
  (e.g. `"{idea} market competitors {target_customer}"`)
- Parse Tavily's response into the shared contract shape: `{ summary, results: [{ title,
  snippet, url }] }` — write a short summary from the top results, don't just dump raw
  Tavily output
- Wrap the call in a FastAPI (or Flask) endpoint `POST /validate` so the frontend has
  something to hit — coordinate the exact framework choice with Yasaswini's architecture
  doc
- Handle: missing/invalid API key (clear error message, not a stack trace), Tavily
  returning zero results, Tavily timeout/rate limit — each should return a clean JSON
  error the frontend can render instead of crashing
- Write a few example queries + expected output in `docs/` or a test file so others can
  verify it works without needing their own API key

### 3. Frontend (React + Tailwind) — Anu Kumari
- Scaffold the app with Vite (`npm create vite@latest -- --template react`) + Tailwind
  CSS, following [`frontend-spec.md`](frontend-spec.md) for layout, palette, typography
- Build `IdeaForm`: idea (textarea), target customer (input), problem (textarea), submit
  button — client-side validation (idea field required, inline error message, no
  browser `alert()`)
- On submit, call `POST /validate` (per the API contract) with a loading state on the
  button while waiting
- Build `ValidationResults`: render the summary plus a card grid of `{ title, snippet,
  url }` results returned by Varshini's agent
- Build `EmptyState` (no results) and `ErrorState` (API failed/timed out) — never leave
  the UI blank or frozen
- Add hover/focus transitions on interactive elements, and confirm the layout is usable
  on a mobile viewport before handing off to Yalene
- Keep the API base URL in an env variable (e.g. `VITE_API_URL`) so it's easy to point
  at local vs. deployed backend

### 4. Integration + Deployment — Yalene
- Once #2 and #3 are individually working, connect them end-to-end locally: run the
  Tavily agent backend and the React frontend together, confirm a real submission
  returns real results on the page
- Update `render.yaml` for the new architecture (likely two services: frontend static
  site/web service + backend web service — confirm shape with Yasaswini's architecture
  doc) and add the Tavily API key as a Render environment variable, not committed to
  the repo
- Deploy both services to Render and verify the live URL works the same as local
- Manual test pass before sign-off: empty idea submission, Tavily API failure/timeout,
  very long idea text, mobile viewport, slow network (throttle in devtools)
- Update the root [`README.md`](../README.md) once the new stack is live — replace the
  old single-Streamlit-service description with the actual frontend/backend split and
  how to run each locally

## API Contract (draft — team lead to finalize in architecture doc)

```
POST /validate
Request:  { idea: string, targetCustomer: string, problem: string }
Response: {
  summary: string,
  results: [{ title: string, snippet: string, url: string }]
}
```

## Timeline (deadline: Aug 28)

| Day | Date | Focus | Owner(s) |
|---|---|---|---|
| Day 1 (AM) | Aug 25 | Kickoff: skim milestone guide, agree on stack (React+Tailwind, FastAPI, Tavily) | All |
| Day 1 (PM) | Aug 25 | Draft + finalize architecture doc, lock API contract | Yasaswini |
| Day 2 | Aug 26 | Build Tavily agent (`search_market` + `/validate` endpoint) in parallel with frontend scaffold + `IdeaForm` | Varshini, Anu Kumari |
| Day 3 (AM) | Aug 27 | Finish `ValidationResults`, `EmptyState`/`ErrorState`; finish agent error handling | Varshini, Anu Kumari |
| Day 3 (PM) | Aug 27 | Local end-to-end integration (frontend calling live agent) | Yalene |
| Day 4 (AM) | Aug 28 | Deploy to Render, update `render.yaml` + env vars, smoke test | Yalene |
| Day 4 (PM) | Aug 28 | Final test pass (empty input, API failure, mobile), README update, submit | All |

This is tight — architecture must be locked by end of Day 1 so #2 and #3 aren't blocked.
No slack days built in, so flag delays immediately rather than waiting for the next
checkpoint.

## What to Submit (per milestone guide)

- System Architecture doc (in repo)
- Working idea submission interface (frontend)
- Web Search Agent connected to Tavily, returning real results to the interface

Focus on end-to-end working first — polish after the flow works.
