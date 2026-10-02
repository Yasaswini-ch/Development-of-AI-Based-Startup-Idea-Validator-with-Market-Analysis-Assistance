# Frontend Design Spec — Idea Submission Interface

> **Note (post-implementation, corrected 2026-09-26):** the palette/typography sections
> below are the original spec. What actually shipped is a **light, warm "editorial
> dossier"** theme defined as tokens in `frontend/src/index.css` (Tailwind v4 `@theme`):
> cream page `surface` `#f6f2ec`, off-white `panel` `#fffdfa`, coral `accent` `#e0654b`,
> teal `info`, sage `success`, brick `danger`. Three fonts: **Fraunces** (serif, headings
> and big numbers), **Inter** (body) and **JetBrains Mono** (small uppercase labels and
> pills). There is no dark mode. An earlier version of this note described a near-black
> monochrome theme; that is no longer accurate.

> **Update 2026-09-26: views beyond the submission form.** This spec only covered the
> Milestone 1 submission page. The app now also has:
> - **AccountMenu** (`components/AccountMenu.jsx`): one account button in the header
>   (showing the signed-in email) that opens a dropdown with History, Compare ideas,
>   Dashboard, Platform health (admins only) and Sign out. It replaced a row of four
>   separate pill buttons. Closes on outside click and Escape.
> - **Dashboard** (`components/AnalyticsDashboard.jsx`): signed-in founder analytics with
>   four sub-tabs: Overview (KPI cards, score bars, a five-axis viability radar including
>   `competitionClarity` and `timing`, assumption-risk and revenue-model charts, SWOT
>   theme cloud), Comparison matrix, Validation history, Score trends.
> - **Platform health** (`components/PlatformHealth.jsx`): admin-only operational view
>   with a 7d/30d/90d filter, KPI cards and charts from `GET /admin/platform-metrics`.
> - **Compare ideas** (`components/CompareIdeas.jsx`) and **History**
>   (`components/HistoryPanel.jsx`).
> - Charts are hand-rolled SVG in `components/charts.jsx` (no chart library), using the
>   palette tokens in `src/index.css`.
>
> See [doc 22](22_AFFINITY_MILESTONE_5_ANALYTICS_DASHBOARDS_AND_ACCESS_CONTROL.md) for
> details.

> **Update 2026-09-26: five-pillar components.** The results view is a pill tab bar
> (Evidence, Market & Rivals, Customers, Gaps & Exposure, Build & Ship, Roadmap) under the idea dossier,
> KPI strip, executive summary, verdict card and confidence dashboard. Sprints 1–4 added,
> inside existing tabs:
>
> | Component | Tab / parent | Renders |
> |---|---|---|
> | `ProvenanceBadge.jsx` | Every tab (market size, viability axes, personas, uncited claims, wedges, Estimate labels) | The one evidence scale: Grounded / Partly grounded / Inferred; accepts a computed `provenance`, bare `sourceIds`, or a `status`/`label` override |
> | `VoiceOfMarketCard.jsx` | Customers, after the personas | `marketOpportunity.voiceOfMarket` quotes with dimension label, speaker and citation |
> | `MarketViabilityIndex.jsx` | Market & Rivals, last block of `MarketOpportunity` | `marketOpportunity.viabilityIndex` scorecard (dots, rating, rationale, citation, badge) and a small "x.x / 5 average"; anchor `sec-dynamics` |
> | `ComparisonMatrix` in `CompetitorAnalysis.jsx` | Market & Rivals, Competitive field | `competitors.comparisonMatrix` table (deep mode) |
> | `StrategicWedgeCard.jsx` | Gaps & Exposure, after the whitespace cards | `whiteSpace.blueprints`; first card open, others show the wedge and key risk; conviction pill on the evidence scale |
> | `MvpDeliveryRoadmap.jsx` | Roadmap tab, above the validation plan (`MvpRecommendations` links to it) | `mvp.deliveryRoadmap` phase cards with week ranges from `lib/timeline.js`, Estimate pill, team sizing |
> | `GtmCommercialModel.jsx` | Build & Ship, end of `GtmStrategy` | `gtm.commercialModel` Estimate pill, "Based on" chips from `basis`, 4 stat tiles and 3 pricing tiers |
> | `GoogleSignInButton.jsx` | `LandingPage.jsx` (signed-out visitors) and `AuthPanel.jsx` (above the email form) | Google Identity Services button; renders nothing without `VITE_GOOGLE_CLIENT_ID` |
>
> Every new component returns `null` when its field is missing, so older sessions still
> render. Contracts: [doc 23](23_AFFINITY_FIVE_PILLAR_EVIDENCE_STRATEGY_AND_GOOGLE_SSO.md).

**Stack**: React (Vite) + Tailwind CSS. No component library — build custom for a
distinct, non-templated feel.

## Layout
- Centered single-column form, max-width ~640px, generous vertical rhythm (not
  edge-to-edge, not cramped)
- Hero/header: product name + one-line tagline, minimal
- Form card: soft shadow, rounded corners (`rounded-2xl`), subtle border — feels like a
  "panel," not a raw form
- Results section appears below the form after submission (same page, smooth
  scroll/fade-in — no jarring reload)

## Palette
- Neutral-dark base (near-black or deep navy background) OR clean white — pick one,
  don't mix light/dark half-heartedly
- One accent color (e.g. indigo/violet or emerald) used sparingly — CTA button, active
  states, metric highlights
- Avoid default Tailwind blue-500/gray palette as-is; tune shades so it doesn't look
  like a template

## Typography
- One display font for headings (e.g. Inter Tight, Geist, or similar modern sans), one
  for body — or one family at varied weights
- Clear hierarchy: large bold heading, muted subtext, readable form labels (not
  placeholder-only labels)

## Components Needed
1. `IdeaForm` — idea (textarea), target customer (input), problem (textarea), submit
   button with loading state
2. `SubmitButton` — disabled/loading/default states, subtle hover transition
3. `ValidationResults` — renders search-agent output: summary panel, then results
   grouped by search angle (Market size & trends, Competitors, Customer demand, ...),
   capped at 3 cards per group with a "Show more" expand — not a flat wall of cards
4. `EmptyState` / `ErrorState` — for no results or failed API call (must not just blank
   out)

## Interaction Details ("premium," not "vibecoded")
- Button and input hover/focus states (subtle scale or border-color transition, not
  default browser outline)
- Loading spinner or skeleton while waiting on the Tavily search agent — never a frozen
  UI
- Form validation inline (e.g. red border + message under empty idea field), not a
  browser alert
- Consistent spacing scale (stick to Tailwind's default spacing tokens, don't hand-pick
  random px values)

## API Contract
See [doc 07](07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md) for the full contract. Summary:

```
POST /validate
Request:  { idea, targetCustomer, problem }
Response: { summary, results: [{ title, snippet, url, query, angle, score }] }
```

That was the Milestone 1 contract. The current, much larger response shape is in
[`architecture.md` §4](architecture.md#4-api-contract) and [doc 07](07_AFFINITY_REST_API_INTERFACE_SPECIFICATION.md).
