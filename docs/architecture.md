# System Architecture — Milestone 1 & 2

Owner: Yasaswini · Status: Milestone 1 complete, Milestone 2 in progress (updated Sep 2026)

## 1. System Overview

The system has four pieces:

1. **Frontend** — React + Tailwind app. Renders the idea submission form and displays
   validation results.
2. **Backend API** — a small FastAPI service exposing `POST /validate`. Receives the
   submitted idea, runs it through the agent pipeline, and returns a shaped response.
3. **Web Search Agent** (Milestone 1) — a Python module that searches the web (Tavily
   when configured, otherwise DuckDuckGo/Wikipedia/Hacker News as a free fallback) for
   market/competitor information related to the submitted idea.
4. **Market Opportunity & Competitor Discovery Agents** (Milestone 2) — two more agents
   that run after the Web Search Agent, reasoning over its real results (context
   passing) to produce structured market analysis and competitor comparison.

Flow at a glance:

```mermaid
flowchart TD
    User(["Founder"]) -->|submits idea| Frontend["React + Tailwind\nfrontend/"]
    Frontend -->|POST /validate| Backend["FastAPI\nbackend/main.py"]
    Backend --> Pipeline["LangGraph Pipeline\nagent/graph.py"]

    Pipeline --> Retrieval["Multi-angle Retrieval\nagent/retrieval.py"]
    Retrieval --> Tavily["Tavily API\n(primary)"]
    Retrieval -.fallback.-> Free["DuckDuckGo + Wikipedia\n+ Hacker News\n(zero-cost)"]

    Pipeline --> WS["Web Search Agent\nagent/crew_agents.py"]
    WS --> MO["Market Opportunity Agent\nagent/market_agent.py"]
    MO --> CD["Competitor Discovery Agent\nagent/competitor_agent.py"]
    WS --> LLM["Groq LLM\nqwen3.6-27b"]
    MO --> LLM
    CD --> LLM

    Retrieval --> Response["summary + results +\nmarketOpportunity + competitors"]
    CD --> Response
    Response --> Backend
    Backend -->|JSON| Frontend
    Frontend -->|renders results| User
```

The frontend never talks to the search sources directly — it only ever calls our own
backend. This gives us one place to shape/validate responses before they reach the UI.

## 2. Agent Breakdown

Agents are built with **CrewAI** and orchestrated by a **LangGraph** `StateGraph`. Each
pipeline stage is one LangGraph node wrapping one CrewAI crew (agent + task, no tools
for the M2 agents — see below). This was deliberate from Milestone 1 even with only
one agent: it means Milestone 2+ agents are added as new graph nodes without
restructuring the backend, which is exactly what happened.

None of the M2 agents use CrewAI's `output_pydantic`/function-calling for structured
output — that proved unreliable with our tested Groq model (repeated "tool_use_failed"
errors, then silent fallback to garbage text). Instead every agent's task asks for
plain JSON in its answer, which we parse ourselves via balanced-brace scanning (finds
a valid JSON object even if the model rambles through a scratchpad first) and validate
against a strict shape before trusting it — falling back to a safe default otherwise.
See `agent/output_guard.py` for the shared reasoning-leak detection used across agents.

### Web Search Agent (Milestone 1)

- **Input**: `{ idea, targetCustomer, problem }` from the submitted form
- **CrewAI role**: "Web Search Agent" — goal: retrieve live, relevant market/competitor
  data; tool: web search (Tavily primary, DuckDuckGo/Wikipedia/Hacker News fallback)
- **LangGraph node**: `web_search` — runs two things: (1) `agent/retrieval.py` expands
  the idea into 5 search angles (market size & trends, competitors, industry news,
  customer demand, how others solve this problem — see diagram below), fetches up to
  8 results per angle,
  drops academic/research-paper domains (arXiv, ResearchGate, IEEE, etc. — not useful
  signal for a founder), dedupes by URL, and ranks the rest — all directly in code, and
  (2) the CrewAI crew produces a short plain-text summary. Results never pass through
  the LLM, so they can't be paraphrased or invented — only the summary paragraph is
  LLM-generated, and even that goes through a quality gate (see Error Handling Policy)
  before it's trusted.
- **Output**: `{ summary, results[] }` where `results` is
  `{ title, snippet, url, query, score }[]` — `query` is which search angle surfaced
  that result, `score` is a computed relevance score (word-overlap between the query
  and the result's text, since these free sources don't provide their own ranking)

![The five research angles a submitted idea is expanded into](images/five-research-angles.svg)

### Market Opportunity & Customer Segmentation Agent (Milestone 2)

- **Input**: the Web Search Agent's real results (context passing — no re-searching)
- **CrewAI role**: "Market Opportunity & Customer Segmentation Analyst" — no tools,
  reasons only over the search results given to it
- **LangGraph node**: `market_opportunity` — runs after `web_search`
- **Output**: `{ marketSize, trends[], segments[], opportunityScore }` where each
  `segments[]` entry is `{ segment, painPoints, motivations, buyingBehavior }` — all
  four fields required per segment (not just a segment label), per the Milestone 2
  guide's requirement to surface pain points, motivations, and buying behavior, not
  just customer types. `opportunityScore` is a Milestone-2-stretch stub (`0` for now).

### Competitor Discovery & Comparison Agent (Milestone 2)

- **Input**: the Web Search Agent's real results (same context-passing pattern)
- **CrewAI role**: "Competitor Discovery & Comparison Analyst" — no tools, identifies
  competitors that actually appear in the given sources rather than inventing names
- **LangGraph node**: `competitor_discovery` — runs after `market_opportunity`, last
  in the current chain
- **Output**: `{ competitors[] }` where each entry is
  `{ name, offering, url, gap, estimatedPrice, featureBreadth }` — `url` is copied
  from the actual source it was found in (not invented), `gap` is the specific weak
  spot this competitor doesn't address, and `estimatedPrice`/`featureBreadth` are
  LLM-estimated categorical values (`"unknown"` when the sources don't support a
  guess) rather than verified data — labeled as such in the UI.

**Future extension point (Milestone 3+):** SWOT/Risk, MVP Recommendation, GTM, and
Report Generation agents each become a new CrewAI crew wrapped in a new LangGraph node,
wired into the same graph with `add_edge`. LangGraph's state dict carries each stage's
output forward so later agents can consume earlier agents' results (context passing),
and partial failures are handled per-node rather than crashing the whole pipeline.

## 3. Data Flow

1. User fills in idea / target customer / problem and submits the form
2. Frontend sends `POST /validate` with the form data
3. Backend validates input (idea field required, non-empty)
   - If invalid → return `400` with `{ error: "..." }`, frontend shows inline field error
4. Backend calls the Search Agent, which expands the idea into several search angles
   and queries Tavily per angle (falling back to DuckDuckGo/Wikipedia/Hacker News per
   angle if Tavily isn't configured or fails)
   - If every source fails for every angle → backend returns `502` with
     `{ error: "..." }`, frontend shows an `ErrorState` ("couldn't fetch results, try
     again")
   - If search returns zero results → backend returns `200` with `{ summary: "...",
     results: [] }`, frontend shows an `EmptyState` ("no market data found for this
     idea")
5. The Market Opportunity Agent runs next, reasoning over the same real results —
   never re-searches, never sees an error state without also skipping (see node code:
   `if state.get("error"): return state`)
6. The Competitor Discovery Agent runs last, same pattern
7. Backend shapes the combined response into the shared contract and returns `200`
8. Frontend renders the summary, market opportunity, competitor analysis, and grouped
   result cards below the form

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend - /validate
    participant S as Search - Tavily or fallback
    participant L as Groq LLM

    U->>F: Fill form, submit
    F->>B: POST /validate
    alt idea is empty
        B-->>F: 400 (error)
        F-->>U: inline field error
    else idea provided
        B->>S: expand into search angles, fetch each
        alt all sources fail
            S-->>B: exception
            B-->>F: 502 (error)
            F-->>U: ErrorState + Try again
        else results returned (possibly empty)
            S-->>B: results list
            B->>L: summarize grounded in results
            L-->>B: summary text
            B-->>F: 200 (summary, results)
            F-->>U: EmptyState (0 results) or grouped result cards
        end
    end
```

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
    { "title": string, "snippet": string, "url": string, "query": string, "angle": string, "score": number }
  ],
  "marketOpportunity": {
    "marketSize": string,
    "trends": [string],
    "segments": [
      { "segment": string, "painPoints": string, "motivations": string, "buyingBehavior": string }
    ],
    "opportunityScore": number   // stub, always 0 until the Milestone 2 stretch feature lands
  },
  "competitors": {
    "competitors": [
      {
        "name": string,
        "offering": string,
        "url": string,
        "gap": string,
        "estimatedPrice": "low" | "mid" | "high" | "unknown",
        "featureBreadth": "narrow" | "moderate" | "broad" | "unknown"
      }
    ]
  }
}

Response 400 / 502:
{
  "error": string
}
```

`marketOpportunity.segments` and `competitors.competitors` can be empty arrays (not
missing keys) when the corresponding LLM call fails or its output can't be validated —
the frontend renders nothing for that section in that case rather than an error, since
the summary + real search results are still valid and shown regardless.

This contract is locked for Milestone 1/2 — Sashi (competitor agent), Yalene
(orchestration), and Anu Kumari (frontend) should build against this without needing to
sync on every field.

## 5. Tech Stack Decisions

| Layer | Choice | Why |
|---|---|---|
| Frontend | React (Vite) + Tailwind CSS | Team wants a premium, polished UI — faster to achieve with component reuse + utility classes than hand-rolled CSS. **Note:** this deviates from the milestone guide's plain HTML/CSS/JS wording; flagging that explicitly since it's a deliberate call. |
| Backend | FastAPI | Lightweight, async-friendly, minimal boilerplate for a single endpoint, easy to extend with more agents later. |
| Orchestration | LangGraph | Owns pipeline state and node wiring — each agent is a graph node, so M2-M4 agents are added without restructuring the backend. |
| Agents | CrewAI | Role/goal-based agent definitions, one Agent+Task per pipeline stage — matches the brief's named-agent structure directly. Only the Web Search Agent uses a tool; the M2 reasoning agents (Market Opportunity, Competitor Discovery) take real data as context instead, since tool-calling proved to be the source of the reasoning-leak bug. |
| Search | Tavily API (primary), DuckDuckGo + Wikipedia + Hacker News (fallback chain) | Tavily gives a real, trained relevance score and reliable results — used whenever `TAVILY_API_KEY` is set. If it's missing or fails, the app falls back to the zero-cost chain (own computed relevance score) instead of erroring out. Tried DuckDuckGo as sole primary first, but its unofficial scraping library proved too flaky (empty or irrelevant results, inconsistent run to run) to trust for a live demo. Academic/research-paper domains are filtered out per mentor guidance — they read as literature review material, not market/competitor signal. |
| Reasoning LLM | Groq (via CrewAI/LiteLLM) | Default provider for agent reasoning (`groq/qwen/qwen3.6-27b`), configurable via `LLM_MODEL` + provider API key (`GROQ_API_KEY`). Tried Google Gemini for a higher rate limit, but its current models were incompatible with our LiteLLM version (2.x deprecated for new keys, 3.x needs newer message formatting) — reverted to Groq. The model occasionally leaks raw ReAct-style reasoning text into its answer, so the summary output is validated before use (see Error Handling Policy). |
| Product UI | No framework/provider names shown | Per mentor guidance, the UI doesn't surface "CrewAI," "Groq," "Tavily," etc. anywhere — footer/status text describes capability generically ("Multi-agent Pipeline," "Live Web Search") instead of naming the underlying tech. |
| Hosting | Render | Already set up for this repo (see `render.yaml`). |

## 6. Deployment Topology

Two Render web services:

- **`startup-validator-frontend`** — serves the built React app (static site or Node
  web service)
- **`startup-validator-backend`** — runs the FastAPI service; holds `GROQ_API_KEY`
  (required) and `TAVILY_API_KEY` (optional — falls back to free search if unset) as
  Render environment variables (never committed to the repo)

Frontend reads the backend's URL via `VITE_API_URL` (env var, set per environment —
local vs. deployed).

## 7. Error Handling Policy

- Backend never lets a raw exception/stack trace reach the frontend — every failure path
  returns `{ error: string }` with an appropriate status code
- Frontend never shows a blank or frozen screen on failure — every failed/empty state
  renders a specific `ErrorState` or `EmptyState` component with a human-readable message
- Timeouts: each search source call uses a short timeout (5s) so one slow/unreachable
  source doesn't hang the whole request — the pipeline just moves to the next fallback
- LLM output quality gate: the Web Search Agent's summary is rejected (and replaced
  with a clean, results-based fallback sentence) if it contains a line break, markdown
  bold/heading syntax, or telltale reasoning-leak phrases — structural checks proved
  far more robust than matching specific phrases, since the model invents new ways to
  ramble faster than a keyword list can keep up (see `agent/output_guard.py`)
- M2 agents (Market Opportunity, Competitor Discovery) don't use the same text-based
  gate — since their output must be JSON anyway, strict shape validation after
  balanced-brace extraction is a stronger and more precise check: if it parses to
  valid JSON with every required field of the right type, it's used regardless of any
  scratchpad rambling around it; otherwise it falls back to a safe default

## 8. Repo Structure

```
.
├── frontend/          # React + Tailwind app (Anu Kumari)
│   └── ...
├── backend/           # FastAPI app + agent pipeline
│   ├── main.py         # POST /validate route
│   └── agent/
│       ├── graph.py            # LangGraph pipeline: state + node wiring
│       ├── crew_agents.py       # Web Search Agent (Milestone 1)
│       ├── market_agent.py      # Market Opportunity Agent (Milestone 2)
│       ├── competitor_agent.py  # Competitor Discovery Agent (Milestone 2, Sashi)
│       ├── output_guard.py      # shared reasoning-leak detection
│       ├── retrieval.py         # multi-angle query expansion + dedup
│       ├── tools.py             # Tavily (primary) + DuckDuckGo/Wikipedia/Hacker News fallback
│       └── llm.py               # reasoning LLM selection
├── docs/
│   ├── architecture.md        # this file
│   ├── milestone1-plan.md
│   └── frontend-spec.md
├── render.yaml         # updated for two services (Yalene)
└── README.md
```

The existing root-level `app.py` (Streamlit prototype) stays as-is for reference but is
superseded by `frontend/` + `backend/` going forward.
