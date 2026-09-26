# 10. User Guide & Operations Manual
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Operational  

---

## 📑 Document Table of Contents
- [1. User Interface Overview](#1-user-interface-overview)
- [2. Step-by-Step Validation Walkthrough](#2-step-by-step-validation-walkthrough)
- [3. Phrasing Tips for Best Results](#3-phrasing-tips-for-best-results)
- [4. Interpreting Validation Dossier Outputs](#4-interpreting-validation-dossier-outputs)
- [5. Troubleshooting Common Issues](#5-troubleshooting-common-issues)

---

## 1. User Interface Overview

The Affinity web application features a clean, tabbed interface designed for rapid startup validation:

```mermaid
flowchart TD
    Form["Idea Submission Form (Idea, Customer, Problem)"] --> Submit["Click 'Validate Idea'"]
    Submit --> Loader["Loading Step Indicator (Multi-angle Search...)"]
    Loader --> Dossier["Validation Dossier"]

    subgraph Dossier["Validation Dossier Tabs"]
        T1["Evidence (sources + confidence dashboard)"]
        T2["Market & Rivals (market size, TAM/SAM/SOM, competitors grid)"]
        T3["Customers (segments & personas)"]
        T4["Gaps & Exposure (white space, SWOT, bear case, assumptions)"]
        T5["Build & Ship (MVP, revenue models, go-to-market)"]
        T6["Roadmap (experiments & action plan)"]
    end

    Account["Account menu (signed in)"] --> History["History"]
    Account --> Compare["Compare ideas"]
    Account --> Dash["Dashboard"]
    Account -.admins only.-> Health["Platform health"]
```

> Tab names above match the current UI (`ValidationResults.jsx`). Earlier versions of
> this manual described four tabs.

---

## 2. Step-by-Step Validation Walkthrough

### Step 1: Submit Your Idea
1. Open the Affinity web dashboard (e.g. `http://localhost:5173`).
2. **Startup Idea (Required):** Enter a concise 1–2 sentence description of your product concept.
3. **Target Customer (Optional):** Specify the primary demographic or user persona (e.g., *"Freelance photographers"*).
4. **Problem Statement (Optional):** Briefly state the pain point being solved (e.g., *"Manual invoice reminders take hours and clients miss due dates"*).
5. Click **Validate Idea**.

### Step 2: Automated Pipeline Execution
During processing (Milestone 2 measured about 10 seconds for the original pipeline; today's deep mode runs more agents and takes longer, while quick mode is faster), the step indicator displays live status:
- *Step 1:* Expanding idea into 5 research angles...
- *Step 2:* Collecting live web evidence...
- *Step 3:* Evaluating source agreement & market size...
- *Step 4:* Extracting competitors via local spaCy NER...
- *Step 5:* Synthesizing white-space gaps & 0–100 score...

### Step 3: Inspect the Dossier
Review results across the six tabs listed in §1.

### Step 4 (optional): Sign In to Keep a Board of Ideas

You can sign in with **Google** (if the deployment has it configured), straight from
the landing page or from the account page, or with an email and password. The first
sign-in after the app has been idle can take up to a minute while the server wakes up. Using Google with the same email as an existing password account signs
you into that same account.
Signing in is optional; anonymous validation still works. With an account:

1. Click **Sign in** in the header and create an account (email + password of at least
   8 characters). You stay signed in for up to 30 days.
2. Every idea you validate while signed in is saved to your account.
3. Open the **account menu** (your email in the header). It holds:
   - **History**: your past validations. Use **Add to compare** on up to 5 of them.
   - **Compare ideas**: the ideas you added, side by side (score, viability,
     confidence, market size, competitors, top strength/risk, MVP, positioning).
   - **Dashboard**: four tabs.
     - *Overview*: KPIs (ideas validated, average and best score, high-risk
       assumptions, complete runs, average source agreement) and charts, including a
       radar of the five Market Viability axes (see §4.4).
     - *Comparison matrix*: every idea on the account in one table, best idea marked 🏆.
     - *Validation history*: a detailed list of each run.
     - *Score trends*: your score and source agreement over time.
   - **Platform health**: shown only to admin accounts (see §4.12).
   - **Sign out**.

> Saved validations expire **7 days** after their last update, even on an account.
> Export a PDF of anything you want to keep longer.

---

## 3. Phrasing Tips for Best Results

| Field | Recommended Phrasing | Bad Phrasing (To Avoid) |
|---|---|---|
| **Startup Idea** | *"AI invoice management app that locks photo delivery until client pays balance"* | *"An app for photographers"* (Too vague) |
| **Target Customer** | *"Freelance wedding and portrait photographers"* | *"Everyone"* (Too broad) |
| **Problem Statement** | *"Clients delay final balance payments until weeks after event delivery"* | *"Invoices are annoying"* (Lacks specifics) |

---

## 4. Interpreting Validation Dossier Outputs

### 4.1 Validation Summary & Opportunity Score (0–100)
- **Score > 75 (High Viability):** Strong market CAGR, clear customer pain points, and unaddressed white-space opportunities.
- **Score 50–74 (Moderate Viability):** Viable market, but crowded competitor presence or niche target customer size.
- **Score < 50 (High Competition / Low Signal):** Highly saturated market with few market gaps identified.

### 4.2 Confidence Dashboard
- **Overall** gauge: the share of the sources the analysis actually cites that are
  strongly relevant (relevance ≥ 0.5), shown as e.g. *"6/8 sources agree"*. If nothing
  was cited it says "No cited sources yet" instead of 0/0.
- **Tiles:** source coverage, cross-source agreement, direct evidence, average
  relevance and source recency.
- The full method, including why the overall number is not an average of the tiles, is
  in [confidence-and-evidence-scoring-methodology.md](confidence-and-evidence-scoring-methodology.md).

### 4.3 3x3 Competitor Positioning Grid
- **Vertical Axis (Price):** `Low`, `Mid`, `High`.
- **Horizontal Axis (Feature Breadth):** `Narrow`, `Moderate`, `Broad`.
- **Strategy Tip:** Look for empty cells on the grid. An empty cell indicates a **positioning white-space**.

### 4.4 Market Viability Axes (Dashboard radar)
All five are 0–100:
- **Market demand**, **Execution risk** (lower is better) and **Growth** make up the
  headline Market Viability Score.
- **Competition clarity** is how much is known about competitors (the share whose price
  and feature breadth could both be determined). A low value means "we couldn't see
  the field clearly", not "the field is crowded".
- **Timing** blends growth-trend strength with how recent the sources are.
- Clarity and timing are shown but not added into the headline score, because they
  describe how much is known rather than whether the news is good.

### 4.5 TAM / SAM / SOM
The Market & Rivals tab shows TAM, SAM and SOM tiles only for figures a source actually
supports, each with its citation. A missing tier means the sources didn't give that
number, not that it's zero.

### 4.6 Grounded vs. Inferred badges
The report uses one evidence scale everywhere. A green **Grounded** pill means the claim
cites at least one real source (hover to see how many). An amber **Partly grounded** pill
(wedge cards) means some links are sourced and some estimated. A grey **Inferred** pill
means it was estimated from heuristics with no direct source match; treat those claims as
hypotheses to check. Economics and the delivery roadmap carry a grey **Estimate** pill for
the same reason.

### 4.7 Voice of the Market (Customers tab)
Up to four short quotes copied word-for-word from the search results, one per source,
with pain and frustration quotes first. Each quote is labelled with the dimension it was
tagged as (for example *Observed Friction*) and carries a citation marker; click the site
name to open the source. The
section is hidden when no source contains a usable sentence.

### 4.8 Market Viability & Dynamics (Market & Rivals tab)
Five axes scored 1–5 with one sentence each: Demand Urgency, Expansion Velocity, Target
Accessibility, Barrier to Entry / Moat and Capital Efficiency, plus their average out of 5.
The report's one headline score is the verdict score at the top; the Market tab shows
the opportunity score as small secondary text.
This is a more detailed view than the Dashboard radar in §4.4 and uses different axes.
Capital Efficiency is always *Inferred* because it's read from how you describe the idea.

### 4.9 How your idea compares (Market & Rivals tab, deep mode)
A table of up to five dimensions comparing your idea with each profiled competitor.
"unknown" means the sources didn't say, not that the competitor lacks the feature.

### 4.10 Strategic Wedge Blueprints (Gaps & Exposure tab)
The first card opens by default; the others show the wedge and key risk until you
click to expand the chain *Observed Friction → Incumbent Blindspot → Structural
Tailwind → Asymmetric Wedge → Defensibility Moat* for one customer segment. The
conviction % is the share of the four evidence-based links that are actually backed by
a source or profiled competitor data, so 25% means most of the chain is a guess. The
amber box names the weakest link.

### 4.11 Delivery Roadmap (Roadmap tab) and Commercial Economics (Build & Ship tab)
The roadmap sits at the top of the Roadmap tab, above the validation plan, and every
timeline in the report (roadmap phases, GTM launch phases, the 7/30/90-day plan) is
labelled on the same week axis. The roadmap turns the MVP features into Alpha, Beta and GA phases with a length in weeks
and an exit gate for each. Commercial Economics shows an estimated CAC range, target
ARPU, payback period, LTV:CAC and three pricing tiers. Both are **rule-of-thumb
estimates** from your competitors' price level, GTM channel fit and SWOT risk, not a
financial forecast; the "Based on" chips show which inputs were used. Use them as a starting point for your own model.

### 4.12 Platform Health (admins only)
Admins (accounts listed in the backend's `ADMIN_EMAILS`) see a 7/30/90-day view of
total validations, cache hit rate, LLM success rate, deep-analysis rate, average
latency, weekly active users, daily volume, node success rates, model usage, latency
by node, top idea categories, recent errors and email delivery. If the menu item is
missing right after being made an admin, sign out and back in.

---

## 5. Troubleshooting Common Issues

### Issue 1: "Analysis wasn't available for this section"
- **Cause:** Every model in the LLM fallback chain failed for that section (rate limits, provider errors or unusable output).
- **Solution:** Wait 60 seconds and click **Validate Idea** again. Competitor and Evidence tabs remain valid. On a local setup running Ollama, the app may ask for your email so a slower local model can finish the analysis and email it to you; the hosted app doesn't ask.

### Issue 2: Submit Button Is Disabled
- **Cause:** A 5-second cooldown protects the Groq free-tier quota after each submission.
- **Solution:** Wait 5 seconds for the cooldown to clear.

### Issue 3: Stale Dashboard Render
- **Cause:** Browser `sessionStorage` cache.
- **Solution:** Open DevTools Console (F12) and run `sessionStorage.clear()`, then reload.
