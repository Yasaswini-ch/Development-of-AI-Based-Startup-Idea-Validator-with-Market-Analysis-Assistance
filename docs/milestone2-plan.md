# Milestone 2 — Team Plan

Week 3-4 · ~10 Hours · Goal: Market Opportunity Agent + Competitor Discovery Agent,
wired into a sequential orchestration pipeline with the Web Search Agent from Milestone 1.

## Task Division (4 people)

### 1. Market Opportunity & Customer Segmentation Agent — Yasaswini
- LLM-reasoning agent: takes the Web Search Agent's results + the original idea and
  evaluates industry size, trends, and target customer segments
- Define the prompt/reasoning chain that turns raw search results into structured
  output: `{ industrySize, trends[], targetSegments[] }`
- Extend `docs/architecture.md` with this agent's contract (input/output shape) so it
  slots into the pipeline
- Own the LLM provider/prompt-engineering decisions for this and future reasoning agents

### 2. Competitor Discovery & Comparison Agent — Varshini
- Search-based agent (same pattern as the Milestone 1 Web Search Agent): given the idea,
  find existing competitors and pull their offerings via Tavily
- Compare offerings and highlight gaps — this can be a lighter LLM pass on top of the
  search results, or structured extraction (title/offering/differentiator per
  competitor)
- Output shape: `{ competitors: [{ name, offering, url, gap }] }`
- Reuse/extend `backend/agent/search_agent.py` patterns rather than duplicating Tavily
  setup from scratch

### 3. Agent Orchestration + Pipeline Integration — Yalene
- Wire the Web Search Agent (M1) → Market Opportunity Agent → Competitor Discovery Agent
  into one sequential pipeline with context passing (each agent's output feeds the next
  where relevant)
- Update the `/validate` (or a new `/analyze`) backend route to run agents in sequence
  and return a combined response
- Handle partial failure: if one agent fails, decide (with Yasaswini) whether the
  pipeline fails entirely or returns partial results — document this in the
  architecture doc
- Validate outputs using sample startup ideas across different domains (e.g. fintech,
  health, consumer app) — confirm the pipeline behaves sensibly on varied input

### 4. Frontend — Market & Competitor Display — Anu Kumari
- Extend the `ValidationResults` component (or add new components) to render the new
  agent outputs: market opportunity summary + segments, competitor comparison table/cards
- Keep the same premium visual language from Milestone 1 (dark panel, accent color,
  card grid) — no visual regressions on the existing search results section
- Add loading states per pipeline stage if the backend streams/returns agents
  incrementally (coordinate with Yalene on whether this is needed for M2 or deferred)

## What to Submit (per project brief)

- Market Opportunity and Customer Segmentation Analysis Agent (working)
- Competitor Discovery and Comparison Agent (working)
- Sequential pipeline with context passing between agents
- Validated outputs across multiple sample startup ideas
