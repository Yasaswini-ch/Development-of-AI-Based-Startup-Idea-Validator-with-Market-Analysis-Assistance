# 23. The Five-Pillar Upgrade: Evidence, Viability, Parity, Wedge, Economics & Google SSO
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 1.0 · 2026-09-26  
**Code reference:** `staging` after Sprint 4 (`a710a41`)  
**Author:** Yasaswini-ch

---

## 📑 Table of Contents
1. [Overview](#1-overview)
2. [Design rule: deterministic post-processing, no new LLM calls](#2-design-rule-deterministic-post-processing-no-new-llm-calls)
3. [Pillar 1: Provenance badges and Voice-of-Market quotes](#3-pillar-1-provenance-badges-and-voice-of-market-quotes)
4. [Pillar 2: Market Viability & Dynamics Index](#4-pillar-2-market-viability--dynamics-index)
5. [Pillar 3: Competitor profiles and parity grid](#5-pillar-3-competitor-profiles-and-parity-grid)
6. [Pillar 4: 5-vector strategic wedge blueprints](#6-pillar-4-5-vector-strategic-wedge-blueprints)
7. [Pillar 5: GTM commercial economics and MVP delivery roadmap](#7-pillar-5-gtm-commercial-economics-and-mvp-delivery-roadmap)
8. [Platform layer: Google sign-in](#8-platform-layer-google-sign-in)
9. [Where each field lives in the response](#9-where-each-field-lives-in-the-response)
10. [What the new sections do not do yet](#10-what-the-new-sections-do-not-do-yet)
11. [Tests](#11-tests)

---

## 1. Overview

Four sprints on `staging` added five analysis "pillars" and one platform feature on top
of the Milestone 1–5 pipeline:

| Pillar | What the founder sees | Backend module | Frontend component | Shown in tab |
|---|---|---|---|---|
| 1A Provenance | A **Grounded** / **Inferred** pill next to a claim | `agent/output_guard.py` `provenance()` | `ProvenanceBadge.jsx` | Market & Rivals |
| 1B Voice of Market | Up to 4 verbatim quotes from real sources | `agent/voice_of_market.py` | `VoiceOfMarketCard.jsx` | Market & Rivals |
| 2 Viability Index | 5 axes scored 1–5 with a rationale each, plus a 0–100 composite | `agent/viability_score.py` `calculate_viability_index()` | `MarketViabilityIndex.jsx` | Market & Rivals |
| 3 Parity grid | Competitor profiles (direct/indirect, strengths, weaknesses) and an "How your idea compares" table | `agent/competitor_agent.py` `_profile_with_llm()` | `CompetitorAnalysis.jsx` (`ComparisonMatrix`) | Market & Rivals |
| 4 Strategic wedge | Up to 3 expandable Friction → Blindspot → Tailwind → Wedge → Moat cards with a conviction % | `agent/strategic_wedge.py` | `StrategicWedgeCard.jsx` | Gaps & Exposure |
| 5A Commercial model | CAC range, ARPU, payback, LTV:CAC and a 3-tier pricing table | `agent/commercial_model.py` | `GtmCommercialModel.jsx` | Build & Ship (GTM) |
| 5B Delivery roadmap | Alpha / Beta / GA phases with exit gates and team sizing | `agent/delivery_roadmap.py` | `MvpDeliveryRoadmap.jsx` | Build & Ship (MVP) |
| Platform | "Sign in with Google" on the landing page and the account page | `agent/google_auth.py`, `auth.login_with_google()`, `POST /auth/google` | `GoogleSignInButton.jsx` in `LandingPage.jsx` and `AuthPanel.jsx` | Landing / Account |

Every new field is **additive**. Older cached responses without these fields still render,
because each component returns `null` when its data is missing.

## 2. Design rule: deterministic post-processing, no new LLM calls

Pillars 1, 2, 4 and 5 add **no LLM call** and cost none of the shared Groq/Gemini quota.
Each one recombines signals the pipeline has already produced (search snippets, market
segments and trends, competitor data, SWOT risks, MVP features, GTM channels). This
follows the same rule as `opportunity_score.py`, `verdict.py` and `white_space.py`: a
number shown to a founder should come from evidence the app can point to, not from a
model asked to invent it.

Only Pillar 3 uses a model, and only in deep mode (see §5).

Each post-processor is wired into `agent/graph.py` inside **its own `try/except`**, so a
bug in it records a node failure (`_record_node_failure`) and leaves the parent section
unchanged instead of blanking it:

| Post-processor | Runs inside node | Attaches to |
|---|---|---|
| `extract_voice_of_market(results)` | `market_opportunity_node` | `marketOpportunity.voiceOfMarket` |
| `calculate_viability_index(...)` | `viability_score_node` (needs SWOT and competitors, which only exist by then) | `marketOpportunity.viabilityIndex` |
| `build_strategic_wedges(...)` | `white_space_node` | `whiteSpace.blueprints` |
| `build_delivery_roadmap(mvp)` | `mvp_node` (skipped when `mvp` is `null`) | `mvp.deliveryRoadmap` |
| `build_commercial_model(...)` | `gtm_node` | `gtm.commercialModel` |

## 3. Pillar 1: Provenance badges and Voice-of-Market quotes

### 3.1 Provenance

```python
provenance(source_ids) -> {"status": "grounded" | "inferred", "sourceCount": int}
```

A claim is **grounded** when it still cites at least one source after sanitising and
verification, otherwise **inferred**. `ProvenanceBadge.jsx` renders the computed shape
when present, and derives the same shape from a bare `sourceIds` array otherwise, so
it can never disagree with what `verification.py` kept.

Where it currently appears:
- next to the market-size sentence (TAM + SAM + SOM source ids combined);
- on each of the five Viability Index axes.

Trends, segments, SWOT items and GTM claims still show the older `Citation` popover
only. See [Known Limitations §7](known-limitations-and-future-work.md#7-five-pillar-features).

The relationship to the confidence tiles: the Confidence Dashboard's
`directEvidenceRatio` counts the same grounded/inferred split across all claims, while
the badge shows it per claim. See
[confidence methodology](confidence-and-evidence-scoring-methodology.md).

### 3.2 Voice of Market

`extract_voice_of_market(results, limit=4)` splits each search snippet into sentences and
keeps the **first** sentence per source that:
- is 40–220 characters long after cleaning (trailing "…" is removed so a cut-off snippet
  doesn't read as fabricated), and
- matches one of three keyword lists, checked in this order: **Observed Friction**
  ("frustrat", "manual", "expensive", ...), **Demand Signal** ("looking for", "would pay",
  ...), **Structural Tailwind** ("growing", "CAGR", "billion", ...).

Quotes are ranked friction first and capped at one per source, so one loud page can't fill
the section. Each quote carries a sentiment (`negative_towards_incumbent`,
`positive_market_signal`, `neutral`), which only sets the card's left-border colour.

```typescript
voiceOfMarket: Array<{
  quote: string;             // copied verbatim from the snippet, never paraphrased
  speakerOrSource: string;   // "Reddit thread", "Hacker News discussion", or the hostname
  sourceId: string;          // "src-N", same numbering as compact_sources()
  url: string;
  sentiment: "negative_towards_incumbent" | "positive_market_signal" | "neutral";
  taggedDimension: "Observed Friction" | "Demand Signal" | "Structural Tailwind";
}>
```

If no snippet has a usable sentence the list is empty and the section is hidden. There is
never a placeholder quote.

## 4. Pillar 2: Market Viability & Dynamics Index

Not to be confused with the headline `marketViability` score (doc 22 §4), which is
unchanged and still feeds the verdict and Dashboard radar. The index is a separate,
more explanatory breakdown.

Each axis is computed as a 0–100 percentage, then mapped to 1–5
(`1 + round(percent / 25)`, clamped). Rating: 4–5 **High**, 3 **Medium**, 1–2 **Low**.
The composite is the mean axis score rescaled to 0–100.

| Axis | Inputs | Cited sources |
|---|---|---|
| Demand Urgency | `0.6 × marketDemand + 40 × min(1, painSignals / 3)`, where pain signals = friction/demand quotes + source-backed segments | quote and segment source ids |
| Expansion Velocity | growth-trend strength (same as `marketViability.growthVelocity`) | sourced trends plus TAM/SAM/SOM |
| Target Accessibility | `60 × share of segments with a concrete buying behaviour + 40 if any Reddit/HN/Product Hunt/Indie Hackers source exists` (25 when no segments) | those segments and community sources |
| Barrier to Entry / Moat | mean of "room" from competitor count (0 → 50, ≤2 → 75, ≤4 → 55, more → 35) and `100 − executionRisk` | competitor URLs and SWOT risks |
| Capital Efficiency | keyword match on the idea: capital-heavy (hardware, biotech, logistics...) 30, capital-light (SaaS, app, API...) 80, otherwise 50 | none: always **Inferred** |

An axis with no citable evidence reports an empty `sourceIds` list, so the UI labels it
Inferred instead of borrowing a neighbour's citations.

```typescript
viabilityIndex: {
  compositeScore: number; // 0-100
  dimensions: Array<{
    name: "Demand Urgency" | "Expansion Velocity" | "Target Accessibility" | "Barrier to Entry / Moat" | "Capital Efficiency";
    score: 1 | 2 | 3 | 4 | 5;
    rating: "High" | "Medium" | "Low";
    rationale: string;
    sourceIds: string[];
    provenance: { status: "grounded" | "inferred"; sourceCount: number };
  }>;
}
```

The UI shows it as a scorecard (dots per axis, rationale, badge), not a radar chart,
because five rationale sentences need reading room.

## 5. Pillar 3: Competitor profiles and parity grid

NER-only discovery (doc 14) is unchanged. In **deep mode only**
(`profile = mode != "quick"`), `analyze_competitors` makes one bounded LLM call
(`_profile_with_llm`, prompts `competitor_profile_*.md`) grounded in each competitor's
own source text. It adds, per competitor:

```typescript
classification: "direct" | "indirect" | "unknown";
pricing: string;        // ≤80 chars, "unknown" when silent
businessModel: string;  // ≤80 chars
strengths: string[];
weaknesses: string[];
gap: string;            // idea-specific, replaces the generic gap disclosure
```

and a top-level `comparisonMatrix` (at most 5 rows):

```typescript
comparisonMatrix: Array<{ dimension: string; idea: string; competitors: Record<string, string> }>;
profiled: boolean;
```

Model-invented competitor names are dropped from the matrix, same rule as
`sanitize_source_ids`. On any failure (quota, bad JSON) the NER-only result is returned
with `profiled: false`, so this pass can never turn a working competitor section into a
failed one. The UI renders the richer card fields and the matrix only when present, with
a note that "unknown" means the sources were silent, not that the feature is missing.

Pillar 4 reuses the first profiled competitor's `weaknesses` as the incumbent blindspot.

## 6. Pillar 4: 5-vector strategic wedge blueprints

`build_strategic_wedges(marketOpportunity, competitors, results)` builds one blueprint per
customer segment (at most 3). Each vector is read off existing data:

| Vector | Source | Counts as grounded when |
|---|---|---|
| Observed Friction | the segment's `painPoints` | the segment has `sourceIds` |
| Incumbent Blindspot | first two `weaknesses` of the first listed competitor | that competitor has weaknesses (deep mode) |
| Structural Tailwind | first market trend | the trend has `sourceIds` |
| Asymmetric Wedge | the segment's `motivations` | motivations are present |
| Defensibility Moat | competitor count (0, ≤2, more) | not counted |

`convictionPercent = round(100 × groundedVectors / 4)`. `keyRisk` names the weakest link
(an inferred blindspot first, then an unconfirmed wedge, then a crowded field of more than
4 competitors, else "execution speed"), capped at 200 characters.

```typescript
blueprints: Array<{
  opportunityTitle: string;  // "A focused wedge for <segment>"
  convictionPercent: number; // 0, 25, 50, 75 or 100
  vectors: { observedFriction: string; incumbentBlindspot: string; structuralTailwind: string; asymmetricWedge: string; defensibilityMoat: string };
  keyRisk: string;
  supportingSourceIds: string[];
}>
```

No segments means an empty list and a hidden section. The existing three-field opportunity
cards stay as they are; the blueprints are shown under them.

## 7. Pillar 5: GTM commercial economics and MVP delivery roadmap

### 7.1 Commercial model (`gtm.commercialModel`)

1. **Price tier**: the most common `estimatedPrice` among named competitors; with none
   known, `high` if the idea mentions a capital-heavy or B2B/enterprise keyword, else
   `mid`. Tier → ARPU: low $19, mid $45, high $99 per month.
2. **CAC**: `ARPU × 3 × channel multiplier`, where the multiplier is the mean of the GTM
   channels' fit (high 1.0, medium 1.5, low 2.2; 1.8 with no channels). Shown as a ±30%
   range rounded to $10.
3. **Payback**: `CAC / ARPU` shown as a −25%/+25% range in months.
4. **LTV:CAC**: lifetime months fall linearly from 24 to 6 as SWOT execution risk goes
   from 0 to 100%; `LTV = ARPU × lifetime`.
5. **Pricing tiers**: Starter ($0), Pro (= ARPU), Scale (3 × ARPU, rounded to $10), with a
   fixed feature list per tier.

All values are returned as display strings (for example `"$130 – $190"`,
`"3 – 5 Months"`, `"2.4x"`) with an `economicRationale` sentence. They are estimates from
heuristics, not market data; see §10.

### 7.2 Delivery roadmap (`mvp.deliveryRoadmap`)

| Phase | Deliverables | Duration | Exit gate |
|---|---|---|---|
| 1: Proof of Wedge (Alpha) | the MVP agent's `features` | sum of feature effort (low 0.5, medium 1, high 2 weeks), min 3 | 10 active users complete the core flow with >60% satisfaction |
| 2: Closed Beta Pilot | the MVP agent's `niceToHave` | same rule, min 3 | 3 paying pilot customers or 25 validated idea submissions |
| 3: General Availability | self-serve onboarding, billing, launch readiness | 3 weeks | 30-day retention above 25% |

`teamComposition` is a fixed three-role template (Full-Stack 1.0 FTE, Frontend/Product
1.0 FTE, UI/UX 0.5 FTE). `totalTimelineWeeks` is the sum of the three phases.

## 8. Platform layer: Google sign-in

### 8.1 Flow

1. `GoogleSignInButton.jsx` loads `https://accounts.google.com/gsi/client` and renders
   Google's own button. It renders **nothing** when `VITE_GOOGLE_CLIENT_ID` is unset or
   the script fails to load. It appears in two places: under the landing page's sign-in
   button for signed-out visitors (signs in without leaving the page), and above the
   email form in `AuthPanel.jsx`. On the account page, a "Waking up the server…" notice
   appears if the request takes more than 6 s, which is normal when Render's free-tier
   backend is cold.
2. The button returns a signed ID token. The frontend sends it as
   `POST /auth/google {"idToken": "..."}`.
3. `google_auth.verify_google_id_token()` verifies the signature and audience against
   `GOOGLE_OAUTH_CLIENT_ID` with the `google-auth` library, rejects tokens with no email
   or `email_verified: false`, and returns only `{sub, email, name, picture}` from the
   verified claims.
4. `auth.login_with_google()` looks the user up **by email**. A new email creates a
   passwordless account (`auth_provider = "google"`, `password_hash = NULL`). An existing
   local account with the same email becomes that same account: its `auth_provider` is
   set to `"google"` and its avatar updated. Both paths issue the same 30-day JWT as
   `/auth/login`.

### 8.2 Endpoint

```
POST /auth/google   { "idToken": string }
200 -> { "token": string, "user": { "id", "email", "authProvider": "local" | "google", "avatarUrl": string | null } }
401 -> { "error": "Google sign-in could not be verified. Please try again." }   (or "not configured", "email not verified")
429 -> rate limited (same per-IP AUTH_RATE_LIMIT_PER_MINUTE bucket as signup/login)
```

Google's raw verification errors are never echoed back, since they can contain
attacker-controlled token content.

### 8.3 Schema change (`users` table)

| Column | Change |
|---|---|
| `password_hash` | now nullable (a Google-only account never sets one) |
| `auth_provider` | new, `NOT NULL DEFAULT 'local'` |
| `avatar_url` | new, nullable, only ever set from the verified `picture` claim |

`_migrate_missing_columns` adds both columns on startup. On Postgres it also runs
`ALTER COLUMN password_hash DROP NOT NULL`. SQLite cannot relax a NOT NULL in place, so an
**existing** local SQLite file keeps `password_hash NOT NULL` and a first-time Google
sign-in into it fails until the file is recreated. Fresh SQLite files are created with the
nullable column.

A Google-only account trying the email/password form gets the standard "Incorrect email
or password." error, because `_verify_password` fails closed on a `NULL` hash. Signing up
with that email returns "An account with that email already exists.", so there is
currently no way for a Google-only account to add a password.

### 8.4 Configuration

| Variable | Service | Notes |
|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | backend | Unset → `/auth/google` returns 401 "not configured" |
| `VITE_GOOGLE_CLIENT_ID` | frontend | Same value. Read at **build** time, so changing it needs a frontend redeploy |

Both are declared in `render.yaml` with `sync: false` and must be entered in the Render
dashboard. In Google Cloud Console, the OAuth client's **Authorized JavaScript origins**
must include the frontend URL (and `http://localhost:5173` for local dev), or Google's
button shows an origin error. See [DEPLOYMENT.md](../DEPLOYMENT.md#google-sign-in-optional).

## 9. Where each field lives in the response

```typescript
interface ValidateResponseAdditions {
  marketOpportunity: { /* existing fields */ voiceOfMarket?: VoiceQuote[]; viabilityIndex?: ViabilityIndex } | null;
  competitors: { competitors: Competitor[] /* + profile fields in deep mode */; comparisonMatrix?: MatrixRow[]; profiled?: boolean } | null;
  whiteSpace: { /* existing fields */ blueprints?: Blueprint[] } | null;
  mvp: { /* existing fields */ deliveryRoadmap?: { totalTimelineWeeks: number; teamComposition: TeamMember[]; phases: Phase[] } } | null;
  gtm: { /* existing fields */ commercialModel?: { unitEconomics: UnitEconomics; pricingTiers: PricingTier[] } } | null;
}
```

The same fields are stored in the saved session context and returned by
`GET /reports/{sessionId}`, since `report_assembler.py` copies each section whole.

## 10. What the new sections do not do yet

- **PDF and email exports don't include them.** `pdf_exporter.py` and
  `email_delivery.py` render the pre-sprint sections only; quotes, the index, blueprints,
  pricing and the delivery roadmap appear on screen and in the JSON only.
- **Compare Ideas and the Dashboard don't use them.** Both still compare the headline
  `marketViability` and opportunity scores.
- **Economics and roadmap are templates driven by a few signals.** ARPU has three possible
  values, the pricing features and team composition are fixed, and exit-gate targets are
  the same for every idea. They are starting points, not forecasts.
- **Quote extraction is keyword-based.** A sentence can be tagged "Observed Friction"
  because it contains "problem" or "manual" without being a customer complaint.
- **Account linking is by email.** Signing in with Google converts a matching local account
  to `auth_provider = "google"` (the password still works). There is no separate linked
  identity and no unlink.

These are also listed in [Known Limitations §7](known-limitations-and-future-work.md#7-five-pillar-features).

## 11. Tests

| Area | Backend | Frontend |
|---|---|---|
| Pillars 1 and 2 | `tests/test_sprint1_evidence_viability.py` | `__tests__/Sprint1EvidenceViability.test.jsx` |
| Pillar 3 | `tests/test_competitor_profiling.py` | — |
| Pillar 5 | `tests/test_sprint2_commercial_roadmap.py` | `__tests__/Sprint2CommercialRoadmap.test.jsx` |
| Pillar 4 | `tests/test_sprint3_strategic_wedge.py` | `__tests__/Sprint3StrategicWedge.test.jsx` |
| Google SSO | `tests/test_sprint4_google_auth.py` (verifier mocked, no network) | `__tests__/GoogleSignInButton.test.jsx`, `__tests__/Sprint4GoogleAuth.test.jsx` |
