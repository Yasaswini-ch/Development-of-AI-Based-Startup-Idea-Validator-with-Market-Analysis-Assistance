# Testing: what we test, how, and what the tests do not prove

This is the page to show when someone asks "how is this tested?". It covers the automated
suites (counts below were taken on 4 October 2026), how to run them, what each group guards,
the manual and live checks that sit beside them, and the gaps, stated plainly.

| Suite | Tests | Runs in | Needs API keys? |
|---|---:|---|---|
| Backend (Python `unittest`) | **679** (1 skipped) | about 45 to 60 seconds | No |
| Frontend (Vitest + Testing Library) | **143** | about 30 to 60 seconds | No |
| CI (GitHub Actions) | both suites, plus lint and production build | on every push and pull request | No |

## How to run them

```bash
# Backend: keyless runner (strips API keys, disables the lookup cache, no billed calls)
cd backend && python scripts/run_tests.py

# Frontend
cd frontend && npx vitest run     # or: npm test
```

`scripts/run_tests.py` exists for one reason: our model quota is small and shared, and an early
version of the tests spent real quota. It clears every key from the environment, turns the
lookup cache off (`WEB_CACHE=0`), and keeps the model library from loading `.env`. The single
real-provider test only runs when `GROQ_API_KEY` is set, so CI never makes a billed call.

## What the tests guard

### Backend: 679 tests in 53 files

| Area | Tests | What it protects |
|---|---:|---|
| Model routing and reliability | 55 | Per-agent model split, the fallback chain, key pool with cooldowns, token budgets, timeouts, rejection of malformed model output (`test_llm_*`, `test_agent_model_split`) |
| Retrieval and lookup cache | 46 | Five-angle search, domain filtering, Tavily deep search and page extraction, the shared cache (`test_retrieval_domain_terms`, `test_tavily_deep`, `test_web_cache`) |
| Competitor intelligence | 103 | Name extraction, noise filters, enrichment, profiling, price and breadth estimates, scoring (`test_competitor_*`, `test_noise_filters`, `test_competition_scoring`) |
| Scoring, verdict and strategy | 92 | Viability and opportunity maths, the verdict rules, contradiction detection, strategic wedges, commercial economics, roadmap (`test_viability_score`, `test_verdict`, `test_sprint1`/`2`/`3_*`, `test_contradiction_detector`) |
| Plan, audit and trace | 47 | Validation sprint and interview script, KPI targets, evidence audit, pipeline trace, experiments and action plan, assumption and revenue fallbacks |
| Pipeline, error paths and modes | 97 | End-to-end pipeline with mocked models, forced failures and partial results, quick versus deep mode, milestone regression suites (`test_end_to_end_pipeline`, `test_track_f_error_paths`, `test_quick_deep_mode`, `test_milestone*`) |
| Reports and delivery | 90 | PDF export (including the full-report sections and logo), canonical report assembly, report email, background jobs and the email gate (`test_pdf_*`, `test_report_assembler`, `test_async_email`) |
| Accounts and security | 57 | Signup and login, password reset (single-use, expiring, safe responses), Google sign-in verification, admin bootstrap, guest-session claiming |
| Data, analytics and telemetry | 92 | Persistence, decision history, event log, metrics, Platform Health aggregation, user analytics, idea categorisation |

### Frontend: 143 tests in 34 files

| Area | Tests | What it protects |
|---|---:|---|
| Report sections | 66 | Market, competitors, confidence, contradictions, experiments, citations, the main results view and stats |
| New report features | 22 | Evidence audit, pipeline replay, pricing table, validation sprint, what-if verdict (and the scoring arithmetic it mirrors) |
| Landing page | 21 | Hero and Ollie, how-it-works, sample preview, tech stack and comparison, animated sections |
| Accounts | 16 | Account menu, password reset flow, Google sign-in button |
| App flow | 6 | Landing to form to results, privacy of history |
| Platform health and analytics | 12 | Admin dashboard and personal analytics |

## Kinds of test, and what each does

- **Unit tests** check one function, such as a score formula or a name filter, with fixed inputs.
- **Contract tests** check the shape of what the API returns, so the frontend can rely on it.
- **Mocked-pipeline tests** run the whole LangGraph pipeline with model calls replaced by stand-ins.
  They prove the wiring, the order of steps and what happens when a step fails; they cannot prove
  that a real model writes a good answer.
- **Forced-failure tests** break one step on purpose and check that the rest of the report still
  arrives with that section marked as failed (the partial-failure contract).
- **Regression tests** pin bugs we actually hit, for example the invalid-escape repair, run-together
  scraped text in comparison cells, and model answers cut off by a too-small token budget.
- **Property checks on arithmetic.** The browser re-implementation of the verdict scoring
  (`frontend/src/lib/whatIf.js`) has tests that pin it to the backend formula, including how
  halves round.

## Checks that are not automated

These need live providers or human eyes, so they are done by hand and written up:

| Check | Where it is recorded |
|---|---|
| Live cross-industry runs (7 domains) and anti-hallucination review | [08](08_AFFINITY_LIVE_VERIFICATION_AND_TEST_PROTOCOL.md) |
| Milestone 2 live verification, including a forced-failure pass | [milestone2-verification.md](milestone2-verification.md) |
| Bugs found in live testing, with root causes and regression tests | [milestone4-verification.md](milestone4-verification.md) |
| How to load-test five or six concurrent users | [load-testing-plan.md](load-testing-plan.md) |
| A first real report from the deployed site (partly degraded by rate limits), and what it did and did not show | [known-limitations-and-future-work.md](known-limitations-and-future-work.md) section 8.9 |

## What the tests do not prove

Say these before a reviewer finds them:

1. **Answer quality.** Tests with mocked models show the system handles a model's output; they do not
   show the output is good. Quality is judged by reading real reports.
2. **Competitor recall.** We have not measured how many true competitors we find against a labelled
   set. Accuracy so far is judged by inspection.
3. **Score weights are not calibrated** against real startup outcomes. The tests pin the arithmetic,
   not whether the weights are right.
4. **Not everything has run live.** The KPI block and the per-step model names in the pipeline view
   were unit-tested and checked in the UI, but not seen on a report from healthy models, because the
   free-tier quota ran out during testing.
5. **No real-device checks.** Layout was checked in a desktop browser at several widths, not on
   physical phones, and email layout was not checked in Gmail or Outlook.
6. **Load behaviour is planned, not measured** beyond the manual notes in the load-testing plan.

## Adding a test

Backend tests live in `backend/tests/test_*.py` and use `unittest`. Set
`os.environ.setdefault("WEB_CACHE", "0")` at the top of any module that touches retrieval, and mock
model calls rather than making real ones. Frontend tests sit in a `__tests__` folder beside the
component, or next to the file for hooks and libraries.
