# Milestone 3 — Team Plan

Week 5-6 · ~10 Hours · Goal: SWOT/Risk Agent, MVP Recommendation Agent, Go-To-Market
Strategy generation, and a conversational startup advisor for follow-up queries.

## Task Division (4 people)

### 1. SWOT & Risk Analysis Agent — Yasaswini
- LLM-reasoning agent: takes all prior agent outputs (idea, market opportunity,
  competitor comparison) and generates structured Strengths / Weaknesses /
  Opportunities / Threats + a risk assessment
- Output shape: `{ strengths[], weaknesses[], opportunities[], threats[], risks[] }`
- Design the prompt so reasoning is grounded in the actual retrieved data, not generic
  boilerplate — this is graded on "quality and depth," so iterate on prompt quality

### 2. MVP Feature Recommendation Agent + Go-To-Market Strategy — Yasaswini
- MVP agent: prioritizes a core feature set based on market fit and resource
  constraints, using the SWOT output as input
- GTM agent: suggests positioning, channels, and early customer acquisition approach
- Both are reasoning-heavy — can share a prompt-chaining pattern with the SWOT agent
  (same LLM call style, different system prompt per agent)

### 3. Conversational Startup Advisor — split across the team
- **Yasaswini** — conversational AI logic: maintain context from all prior agent
  outputs, answer follow-up questions ("what if I target enterprise instead?"), decide
  the prompt/context-window strategy so the advisor doesn't lose the pipeline's findings
- **Anu Kumari** — chat UI component: message list, input box, streaming/typing
  indicator, styled consistently with the rest of the app
- **Yalene** — backend: new `/chat` (or similar) endpoint, session/conversation state
  handling, wiring the chat UI to the backend

### 4. Search Support + Validation — Varshini
- Extend the Web Search Agent so the Conversational Advisor can trigger a fresh Tavily
  lookup mid-conversation when the user asks something the pipeline didn't already
  cover (e.g. "how big is this market in Europe specifically?")
- Validate the SWOT, MVP, and GTM agent outputs against the search data they're
  supposed to be grounded in — flag any agent that's hallucinating instead of using
  retrieved results
- Support testing across the sample startup ideas from Milestone 2 through the new
  agents

## What to Submit (per project brief)

- SWOT and Risk Analysis Agent (working)
- MVP Feature Recommendation Agent (working)
- Go-To-Market Strategy generation (working)
- Conversational startup advisor for follow-up queries and deeper exploration
