# Milestone 4 — Team Plan

Week 7-8 · ~10 Hours · Goal: Report Generation Agent, end-to-end testing across the full
pipeline, optimization, and final documentation/demo.

## Task Division (4 people)

### 1. Startup Validation Report Generation Agent — Yasaswini
- Compiles every prior agent's output (search results, market opportunity, competitor
  comparison, SWOT/risk, MVP recommendation, GTM strategy) into one structured report
- Output shape: a single document/JSON that the frontend can render and export
  (e.g. `{ ideaSummary, marketOpportunity, competitors, swot, mvp, gtm, generatedAt }`)
- Design this as the final stage of the pipeline — it should not re-derive data, only
  synthesize what earlier agents already produced

### 2. Report UI + Export — Anu Kumari
- Build the report view: a clean, readable layout presenting every section of the
  compiled report (not just raw JSON dumped on screen)
- Add a download/export action (PDF or similar) so founders can save the report
- Keep the same premium design language across the whole report page

### 3. End-to-End Testing + Optimization Lead — Yalene
- Coordinate full end-to-end testing across all agents, search integration, and report
  generation — run the complete pipeline against varied sample ideas and catch breakage
  at any stage
- Own the test pass checklist: empty/invalid input, agent failure mid-pipeline, slow
  API responses, mobile viewport, and the full happy path start to finish
- Final deployment check on Render across the whole app

### 4. Query & Reasoning Optimization — Varshini (search) + Yasaswini (prompts)
- **Varshini** — optimize Web Search Agent and Competitor Discovery Agent query design
  for relevance; reduce noisy/irrelevant Tavily results
- **Yasaswini** — optimize prompt engineering and reasoning quality across the
  Market/SWOT/MVP/GTM/Report agents; tighten outputs based on testing feedback from
  Yalene's pass

### 5. Documentation + Final Demo — All
- **Yalene** — technical documentation: how the full pipeline works, how to run/deploy
  the whole system
- **Anu Kumari** — demo polish: make sure the live app looks and feels ready to present
- **Varshini** — document the search/agent components and their configuration
- **Yasaswini** — project report: overall outcomes vs. the original project brief,
  written summary of the multi-agent architecture and results

## What to Submit (per project brief)

- Startup Validation Report Generation Agent (working, compiles all agent outputs)
- End-to-end tested pipeline across all agents, search integration, and report
  generation
- Optimized search queries, prompts, and reasoning quality
- Technical documentation, project report, and final demonstration
