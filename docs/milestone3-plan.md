# Milestone 3 — Team Plan (Revised)

Goal: SWOT/Risk Agent, MVP Feature Recommendation Agent, GTM Strategy Agent, and a
conversational startup advisor for follow-up queries — all built on the same
LangGraph pipeline pattern established in Milestone 2 — plus 3 stretch features once
the required pieces are done.

---

## Design: the Conversational Advisor

The advisor is **a second, small LangGraph graph** (`chat_turn`) that runs once per
chat message, not a node bolted onto the main pipeline — the main pipeline runs once
per `/validate` request, but a conversation is many turns, so it needs its own graph.

**Session state (new, simple — no DB needed):**
- `POST /validate`'s response gains a `sessionId`
- A small in-memory store (`backend/agent/session_store.py`, a plain
  `dict[str, dict]`) holds that session's full pipeline output — idea, results,
  marketOpportunity, competitors, swot, mvp, gtm — plus the running chat transcript
- Documented limitation: in-memory won't survive a server restart or scale across
  instances — acceptable for milestone scope, consistent with the project's existing
  "Database: None yet" in the README

**The `chat_turn` graph:**
- **`interpret` node** — one LLM call: given the user's message + existing pipeline
  context, decide `{ needsSearch: bool, searchQuery: string | null }`
- **Conditional edge** — if `needsSearch`, go to `chat_search`; otherwise straight to
  `respond`
- **`chat_search` node** — calls `retrieval.collect()` (reusing the existing M1
  function, not rebuilding it) with the LLM-crafted query, folds fresh results into
  context
- **`respond` node** — one LLM call with full context (idea + all prior agent outputs
  + conversation history + any fresh search) → produces the reply

**New endpoint:** `POST /chat` — `{ sessionId, message }` in, `{ reply }` out. The
server owns the transcript (looked up by `sessionId`), so the frontend only ever sends
the latest message, not the whole history each time.

---

## The Contract

**SWOT & Risk Analysis Agent output** (`backend/agent/swot_agent.py`):
```json
{
  "strengths": ["string", "..."],
  "weaknesses": ["string", "..."],
  "opportunities": ["string", "..."],
  "threats": ["string", "..."],
  "risks": [
    { "risk": "string", "severity": "low | medium | high", "likelihood": "low | medium | high" }
  ]
}
```
*(`severity`/`likelihood` are the Phase 2 addition — default to `"unknown"` until then.)*

**MVP Feature Recommendation Agent output** (`backend/agent/mvp_agent.py`):
```json
{
  "features": [
    { "feature": "string", "rationale": "string", "impact": "low | medium | high | unknown", "effort": "low | medium | high | unknown" }
  ]
}
```
*(`impact`/`effort` are the Phase 2 addition — stub as `"unknown"` for now.)*

**GTM Strategy Agent output** (new file `backend/agent/gtm_agent.py`):
```json
{
  "positioning": "string",
  "channels": ["string", "..."],
  "earlyCustomerApproach": "string"
}
```

**`/chat` request/response:**
```json
// Request
{ "sessionId": "string", "message": "string" }

// Response
{ "reply": "string" }
```

**`/validate` response gains:**
```json
{
  "sessionId": "string",
  "swot": { /* shape above, or null if that node failed */ },
  "mvp": { /* shape above, or null if that node failed */ },
  "gtm": { /* shape above, or null if that node failed */ }
}
```

With this locked, everyone builds against these shapes from day one — no one waits on
anyone else's actual implementation landing first.

---

## Phase 1 — Required

### Yasaswini — SWOT & Risk Agent + Chat Reasoning Logic
**Files:** new `backend/agent/swot_agent.py`; the `interpret`/`respond` prompt logic
used by Yalene's `chat_turn` graph

- SWOT & Risk Agent: takes the idea + Market Opportunity + Competitor outputs from M2
  and produces the structured shape above — grounded in the actual retrieved data, not
  generic boilerplate (this is graded on quality/depth, so iterate on the prompt)
- Chat reasoning: write the `interpret` prompt (decide if a message needs a fresh
  search) and the `respond` prompt (answer using full session context) — hand these to
  Yalene as functions/prompt templates she wires into the graph, you don't need to
  touch `graph.py` or the endpoint yourself
- **Depends on:** nothing for the agent — same pattern as `market_agent.py`/
  `competitor_agent.py`. Chat prompts depend on knowing the final session-state shape
  Yalene lands on, so sync with her before finalizing those
- **Done when:** SWOT agent tested on 3+ real ideas returns grounded, non-generic
  output; chat prompts tested manually against a mocked session context

### Sashi — GTM Strategy Agent + MVP Feature Recommendation Agent
**Files:** new `backend/agent/gtm_agent.py`, new `backend/agent/mvp_agent.py`

- GTM Agent: takes idea + market/competitor/SWOT outputs, produces positioning,
  channels, and early customer acquisition approach
- MVP Agent: takes SWOT output as input, prioritizes a core feature set based on
  market fit and resource constraints
- Both follow the same pattern as `market_agent.py`/`competitor_agent.py` — same
  plain-JSON approach, same parse-with-safe-fallback handling
- **Depends on:** nothing — both fully yours to build and test standalone before
  Yalene wires them into the graph
- **Done when:** both agents tested on 3+ real ideas return grounded output matching
  their contract shapes, with fallback paths verified

### Yalene — Chat Infrastructure + Pipeline Wiring
**Files:** new `backend/agent/session_store.py`, `backend/agent/graph.py`,
`backend/main.py`

- Build `session_store.py` (in-memory dict keyed by `sessionId`)
- Wire SWOT/MVP/GTM as new nodes on the main pipeline, same pattern as M2's
  `competitor_discovery`/`opportunity_score` nodes
- Build the `chat_turn` graph: `interpret` → conditional edge → (`chat_search` →)
  `respond`, using Yasaswini's prompt logic
- Add `POST /chat` endpoint and `sessionId` to `/validate`'s response
- **This time, don't repeat the M2 gap:** wrap each new node in its own try/except so
  one agent failing doesn't crash the whole request — carry forward the `errors` field
  pattern from M2, including for the new SWOT/MVP/GTM nodes
- **Depends on:** the contract shapes above — build against mocks/stubs, swap in real
  agent functions as they land
- **Done when:** the full pipeline runs end-to-end with all 6 nodes, killing any one
  node on purpose still returns a 200 with the rest intact, and a chat round-trip
  works against a manually-seeded session

### Anu Kumari — Frontend for All New Data
**Files:** new components for SWOT/Risk, MVP, GTM; new chat UI component

- Build display components for SWOT/Risk, MVP recommendations, and GTM strategy —
  same visual language as the existing Market Opportunity/Competitor components
- Build the chat UI: message list, input box, typing/streaming indicator
- Handle `null` sections gracefully (same pattern as M2 — don't just silently hide,
  show an inline "unavailable" state, unlike the gap M2 shipped with)
- **Depends on:** the contract shapes above — build against mocks first
- **Done when:** all components render correctly against full and partial (null
  section) mock data, and the chat UI can send/receive against a stubbed `/chat`
  response

### Varshini — Search Extension + Validation
**Files:** `backend/agent/retrieval.py` (extend), validation report

- Extend `retrieval.py` so the `chat_search` node can trigger a fresh, scoped search
  mid-conversation (reuse `collect()`, don't rebuild it)
- Validate SWOT, MVP, and GTM outputs against the search data they're supposed to be
  grounded in — flag any agent that's hallucinating instead of using retrieved results
- Test across the Milestone 2 sample ideas plus new conversational scenarios (a
  follow-up question that needs a fresh search, one that doesn't)
- **Depends on:** Phase 1 being functionally complete to fully validate — draft your
  test scenarios and industries now, run them once the pipeline lands

---

## Timeline (dependency order, no dates)

No calendar dates this time — just who can start immediately, who's blocked on what,
and where things merge back together.

**Stage 1 — everyone starts immediately, in parallel**
- **Yasaswini** — SWOT & Risk Agent (no dependency, start now)
- **Sashi** — GTM Agent + MVP Agent, both built and tested standalone against the
  contract's mocked SWOT shape (don't wait for Yasaswini's real SWOT output to start)
- **Yalene** — `session_store.py`, and a first pass at the `chat_turn` graph skeleton
  (`interpret` → conditional edge → `respond`) using placeholder prompts, since
  Yasaswini's real prompts aren't needed to get the graph's shape working
- **Anu** — all new frontend components (SWOT/Risk, MVP, GTM, chat UI), built entirely
  against mocked JSON matching the contract
- **Varshini** — extend `retrieval.py` for `chat_search` (no dependency, purely an M1
  code extension)

**Stage 2 — first merge point, once Stage 1's agents land**
- **Yalene** — swap Yasaswini's, Sashi's real agent output into the pipeline nodes;
  swap in Yasaswini's real `interpret`/`respond` prompts into the `chat_turn` graph
- **Anu** — swap her mocked data for real API responses, fix any shape mismatches
- This is the one point where Yalene is genuinely blocked — she needs Stage 1's three
  agents merged before she can wire the *real* pipeline, though her scaffolding work
  isn't wasted since it's built against the same contract shapes

**Stage 3 — validation, once the full pipeline + chat are wired**
- **Varshini** — validate SWOT/MVP/GTM against real search data, test conversational
  scenarios end-to-end (including a message that should trigger `chat_search`) — this
  is the one role that can't fully start until Stage 2 is done, though test ideas and
  scenarios can be drafted earlier

**Stage 4 — Phase 2 stretch, only after Stage 2 is stable**
- **Yasaswini** — risk severity/likelihood fields (her own file, no new dependency)
- **Varshini** — MVP impact/effort fields (touches Sashi's file — quick sync with him
  first)
- **Anu** — heatmap grid + MVP matrix grid, both can start against mocks as soon as
  Stage 1 finishes, real data swap-in happens once Yasaswini's/Varshini's fields land
- **Yalene** — MVP matrix grid UI, same mock-first approach as Anu
- **Sashi** — "What We've Learned" summary panel, solo — can start as soon as
  `session_store.py` exists in Stage 1, doesn't need to wait for Stage 4 at all

If Stage 2 slips, drop Phase 2 items in this order first: MVP priority matrix → risk
heatmap → summary panel — required pieces and Varshini's validation always take
priority over stretch features.

---

## Phase 2 — Stretch Features (only after Phase 1 is done)

### 1. Risk Severity Heatmap — Yasaswini (backend) + Anu Kumari (frontend)
- Yasaswini: add `severity`/`likelihood` to each risk in her own SWOT/Risk Agent
  output (already stubbed as `"unknown"` in Phase 1)
- Anu: render a small heatmap grid from that data — build against mocked
  severity/likelihood values first
- **Depends on:** Yasaswini's fields landing before the heatmap has real data — Anu's
  component itself can be built in parallel using mocks

### 2. MVP Priority Matrix (Impact vs. Effort) — Varshini (scoring) + Yalene (grid UI)
- Varshini: add `impact`/`effort` scoring fields to Sashi's MVP Agent output (a quick
  handoff/review with Sashi before merging, since this touches his file)
- Yalene: build the frontend impact/effort 2×2 grid
- **Depends on:** Varshini's fields landing before the grid has real data — build the
  grid against mocks in the meantime

### 3. "What We've Learned" Summary Panel — Sashi (solo, full stack)
- Backend: a periodic summarization pass over the chat session's transcript
  (`session_store.py` data) surfacing key pivots/decisions (e.g. "exploring an
  enterprise pivot")
- Frontend: a small, self-contained panel near the chat UI — doesn't need to touch
  anyone else's components
- **Depends on:** nothing beyond the session store existing — entirely his own module
  end-to-end

---

## What to Submit (per project brief)

- SWOT and Risk Analysis Agent (working)
- MVP Feature Recommendation Agent (working)
- Go-To-Market Strategy generation (working)
- Conversational startup advisor for follow-up queries and deeper exploration
- *(Stretch, if time allows)* Risk heatmap, MVP priority matrix, chat summary panel
