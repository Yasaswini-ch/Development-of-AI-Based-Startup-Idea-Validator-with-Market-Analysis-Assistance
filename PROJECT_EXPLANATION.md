# Project Explanation

## Project

**Affinity** is an AI-based startup idea validator with market analysis assistance.
A founder enters an idea, target customer, and problem statement. The app returns
live source evidence, market opportunity analysis, competitor discovery, an
opportunity score, a source-agreement indicator, and a white-space opportunity view.

## What Milestone 2 Adds

Milestone 2 turns the project from a search demo into a decision-support pipeline:

- Market Opportunity Agent: summarizes market size, growth, TAM/SAM/CAGR signals
  where available, trends, and customer segments.
- Competitor Discovery: identifies competitors from real search snippets using
  local spaCy NER rather than another LLM call.
- Opportunity Score: deterministic 0-100 scoring over market and competition
  signals.
- Source Agreement: counts how many retrieved sources mention market growth or
  competitive pressure.
- White-Space Analysis: combines customer pain points, competitor density, and
  evidence snippets into opportunity gaps.

## Why This Architecture

The system uses a FastAPI backend and a React/Tailwind frontend. The backend pipeline
is orchestrated with LangGraph so each stage can pass structured state to the next
stage and fail independently.

The project intentionally avoids making every step an LLM call. Market Opportunity
uses Groq because it needs synthesis and reasoning. Competitor Discovery, Source
Agreement, Opportunity Score, and White-Space Analysis are local post-processing
steps. This keeps the shared Groq quota available for the one step that needs it
most and makes the app more reliable during demos.

## Request Flow

1. The user submits an idea through the React frontend.
2. FastAPI receives `POST /validate`.
3. Retrieval expands the idea into multiple research angles and fetches sources.
4. Market Opportunity runs over the retrieved evidence.
5. Competitor Discovery extracts company/product names from competitor-angle sources.
6. Confidence, Opportunity Score, and White-Space Analysis are computed locally.
7. The frontend renders sources, market analysis, competitors, and opportunity gaps.

## Deployment

Both services are deployed on Render:

- `startup-validator-backend`: FastAPI backend from `backend/`
- `startup-validator-frontend`: React static frontend from `frontend/`

The `staging` branch is used for active development and deployed testing. The `main`
branch is reserved for stable reviewed releases.
