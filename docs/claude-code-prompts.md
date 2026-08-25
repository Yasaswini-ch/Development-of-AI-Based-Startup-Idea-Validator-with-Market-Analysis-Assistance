# Claude Code Prompts — AI Startup Idea Validator

Prompts each teammate can paste into Claude Code to build their assigned piece.
Reference `docs/architecture.md` first in every session so Claude Code has the API
contract and data flow in context. Adjust file paths if the repo structure has moved on
by the time you use these.

## General tip

Start every session with something like:

> Read docs/architecture.md and docs/milestone{N}-plan.md before doing anything. I'm
> [name] working on [task]. Confirm you understand the API contract before we start.

This anchors Claude Code to the actual project decisions instead of guessing.

---

## Milestone 1 (done — kept for reference)

**Backend / Web Search Agent (Varshini):**
> The Web Search Agent is built with CrewAI (backend/agent/crew_agents.py) and Tavily is
> wired in as a tool (backend/agent/tools.py). Tune the agent's goal/backstory and the
> task's description/expected_output in crew_agents.py so results are consistently
> relevant. Handle missing API key, zero results, and timeouts gracefully at the
> LangGraph node level (agent/graph.py) — errors should reach the frontend as
> { error: string }, never a raw stack trace.

**Frontend (Anu Kumari):**
> Following docs/frontend-spec.md, build out frontend/src/components — polish IdeaForm,
> ValidationResults, EmptyState, and ErrorState. Keep the dark-panel + single-accent
> design language. Test on mobile viewport too.

**Integration + deployment (Yalene):**
> Connect frontend/ and backend/ end-to-end locally, then update render.yaml for two
> Render services (frontend + backend) with TAVILY_API_KEY as an env var on the
> backend service, not committed to the repo.

---

## Milestone 2

**Market Opportunity Agent (Yasaswini):**
> Create backend/agent/market_agent.py. It takes the idea and the Web Search Agent's
> results, and uses an LLM call to produce { industrySize, trends[], targetSegments[] }.
> Ground the reasoning in the actual search results passed in, don't let the model
> invent numbers. Add this agent's contract to docs/architecture.md.

**Competitor Discovery Agent (Varshini):**
> Add a new CrewAI Agent+Task to backend/agent/crew_agents.py (e.g.
> build_competitor_crew), reusing the tavily_search tool from tools.py. Given the idea,
> find existing competitors and return { competitors: [{ name, offering, url, gap }] }
> via output_pydantic. Add the schema to agent/schemas.py.

**Pipeline orchestration (Yalene):**
> In backend/agent/graph.py, add market_opportunity and competitor_discovery nodes after
> web_search, wiring them with add_edge so LangGraph passes state (and thus context)
> between them. Decide and document in docs/architecture.md how partial agent failure is
> handled (fail the whole request vs. return partial results) — implement it as
> conditional edges or try/except per node.

**Frontend — market & competitor display (Anu Kumari):**
> Extend frontend/src/components to render the Market Opportunity Agent and Competitor
> Discovery Agent outputs, matching the existing card/panel visual style. Add a
> competitor comparison table or card grid.

---

## Milestone 3

**SWOT & Risk Agent (Yasaswini):**
> Create backend/agent/swot_agent.py. Given the idea and all prior agent outputs
> (market opportunity, competitors), produce
> { strengths[], weaknesses[], opportunities[], threats[], risks[] } via an LLM call.
> Iterate on the prompt so each item is grounded in specific retrieved data, not generic
> startup advice.

**MVP Recommendation + GTM Agent (Yasaswini):**
> Create backend/agent/mvp_agent.py and backend/agent/gtm_agent.py. MVP agent
> prioritizes a feature set based on market fit and resource constraints, using the
> SWOT output as input. GTM agent suggests positioning, channels, and early customer
> acquisition strategy. Reuse the LLM-calling pattern from swot_agent.py.

**Conversational advisor — backend/AI logic (Yasaswini):**
> Design a /chat endpoint in backend/main.py that keeps the full pipeline's findings
> (search, market, competitors, SWOT, MVP, GTM) in context so follow-up questions are
> answered using what's already been retrieved/reasoned, not fresh guesses. Document the
> context-window strategy in docs/architecture.md.

**Conversational advisor — chat UI (Anu Kumari):**
> Build a ChatPanel component in frontend/src/components: message list, input box,
> typing/loading indicator, styled consistently with the rest of the app (dark panel,
> accent color). Wire it to the /chat endpoint.

**Search support for advisor + validation (Varshini):**
> Extend search_agent.py so it can be called mid-conversation by the advisor for
> follow-up lookups the original pipeline didn't cover. Then run the SWOT/MVP/GTM
> agents against 3-4 sample ideas across different domains and flag any output that
> looks disconnected from the actual retrieved data.

---

## Milestone 4

**Report Generation Agent (Yasaswini):**
> Create backend/agent/report_agent.py that compiles every prior agent's output into one
> structured report object per docs/architecture.md's report contract. It should only
> synthesize existing data, not re-query or re-reason from scratch.

**Report UI + export (Anu Kumari):**
> Build a ReportView component in frontend/src/components rendering every section of
> the compiled report in a clean, readable layout, plus a PDF/export download action.

**End-to-end testing (Yalene):**
> Run the full pipeline (search → market → competitors → SWOT → MVP → GTM → report)
> against varied sample ideas. Write down every failure mode you hit — empty input,
> agent timeout, malformed LLM output — and file them as issues before fixing.

**Query/prompt optimization (Varshini + Yasaswini):**
> Varshini: review Tavily query strings across search_agent.py and competitor_agent.py,
> tighten them to reduce irrelevant results.
> Yasaswini: review all agent prompts (market, SWOT, MVP, GTM, report) against Yalene's
> test findings and tighten reasoning quality.

**Documentation (All):**
> Write/update README.md and docs/architecture.md to reflect the final pipeline as
> built, not just as planned — include how to run every agent locally and how the
> deployed system is wired together.
