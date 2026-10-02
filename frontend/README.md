# Frontend

React 19 + Vite + Tailwind 4 single-page app for Affinity. Updated 2026-10-02.

## Run it

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_URL=http://localhost:8000
npm run dev              # http://localhost:5173
```

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Production build |
| `npm run lint` | oxlint |
| `npm test` | Vitest and Testing Library |

`.env` variables: `VITE_API_URL` (the backend) and `VITE_GOOGLE_CLIENT_ID` (optional). **The
Google sign-in button renders nothing unless `VITE_GOOGLE_CLIENT_ID` is set**, so it will not
appear on a local run until you add it.

## What it shows

1. **Landing page** (`LandingPage.jsx`): an interactive "How it works", the agent grid
   (`AgentsGrid.jsx`, data in `agentsData.js`), the tool stack (`TechStack.jsx`) and the
   comparison with general chatbots (`ComparisonTable.jsx`).
2. **Idea form** (`IdeaForm.jsx`): idea, target customer and problem, with a progress line
   while the pipeline runs.
3. **Report** (`ValidationResults.jsx`): eight tabs, with a section navigator inside each.

| Tab | Main components |
|---|---|
| Evidence | source list, `ConfidenceDashboard`, `Citation`, `ProvenanceBadge` |
| Market | `MarketOpportunity` (TAM/SAM/SOM tiers; estimates badged), `MarketViabilityIndex` |
| Competitors | `CompetitorAnalysis` (direct/indirect groups, comparison table, positioning grid) |
| Customers | `CustomerPersonas`, `VoiceOfMarketCard` |
| Gaps | `WhiteSpaceAnalysis`, `StrategicWedgeCard` |
| Risks | `SwotAnalysis`, `BearCase`, `AssumptionTracker` |
| Build & Ship | `MvpRecommendations`, `MvpDeliveryRoadmap`, `RevenueModels`, `GtmStrategy`, `GtmCommercialModel` |
| Roadmap | `ExperimentsActionPlan` |

Around the report: `VerdictCard`, `ContradictionsBanner`, `DegradedBanner` (shown when a
section used a rule-based fallback), `ChatAdvisor` (jumps to the tab and section an answer
came from), and PDF and email actions.

4. **Account views:** `HistoryPanel`, `CompareIdeas`, `AnalyticsDashboard` and (admins)
   `PlatformHealth`, behind `AccountMenu`.

## Behaviour worth knowing

- The last result is kept in `sessionStorage` under `affinity:lastValidation`. When testing a
  change, clear it (`sessionStorage.clear()`) or a stale result can render.
- A section that failed shows an inline message while the others still render.
- The backend may answer `needsEmailForDeepAnalysis` or `202` with a `jobId`; the form handles
  both (`DeepAnalysisPrompt.jsx`).
- Local fixtures live in `src/mocks/validationMock.js`. They use placeholder `example.com`
  URLs and are for tests, not for display.

Backend routes are documented in
[`docs/07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md`](../docs/07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md);
the UI spec is [`docs/frontend-spec.md`](../docs/frontend-spec.md).
