# Milestone 4 — Verification Log (live-testing fixes, September 2026)

**Logged:** 2026-09-26 · **Branch:** `staging` at `4c39380` · **Covers:** fixes committed 2026-09-24 to 2026-09-26

> Out of scope for this log: `ba04577` (merged later the same day), which removed the
> "enter your email" prompt on hosts with no local model and stopped device-local
> history leaking between accounts. It has its own tests in
> `test_deep_analysis_email_gate.py` and `App.historyPrivacy.test.jsx`.

Point-in-time record, in the same spirit as [`milestone2-verification.md`](milestone2-verification.md)
and [doc 08](08_AFFINITY_LIVE_VERIFICATION_AND_TEST_PROTOCOL.md): what broke during live
testing of the deployed app, why, what changed, and which regression test now guards
it. Like those logs, it should not be edited later to describe newer behaviour; add a
new dated log instead.

**Sources of evidence.** Bug descriptions and root causes come from the fix commits
listed with each item (their messages record what was observed live). The regression
tests were re-run for this log on 2026-09-26 against `4c39380`:

| Suite | Command | Result |
|---|---|---|
| Backend regression tests for §1–§4 | `python -m unittest tests.test_llm_fallback_validation tests.test_llm_fallback_chain tests.test_admin_bootstrap tests.test_db_persistence tests.test_auth.IsAdminSelfHealTests` + the three `test_confidence_dashboard_*` tests in `tests.test_milestone3` | **27 tests, OK** |
| Frontend regression tests | `npx vitest run` on `MarketOpportunity`, `AccountMenu`, `ConfidenceDashboard`, `App`, `AnalyticsDashboard`, `PlatformHealth` test files | **6 files, 26 tests, passed** |

A wider run of ten backend test modules in the same environment gave 112 tests with one
failure, `test_milestone3.test_search_angles_use_compact_product_subject`, which is
unrelated to these fixes (search-angle wording). It is noted here rather than hidden.

---

## 1. LLM fallback chain stopped early and skipped healthy models

**Observed:** the market-opportunity step gave up after only 2 of the 4 configured
models: the second model returned invalid JSON three times without ever rate-limiting,
and the request fell straight into the "needs deep analysis, enter your email" gate even
though the remaining models were available.

**Root cause:** `_kickoff_cloud_chain` only advanced to the next model on a rate limit
or `model_not_found`. A model that answered successfully at the network level but with
unparseable or wrongly shaped output was returned as-is. The shape check ran one level
up, in `kickoff_with_fallback`, **after** the chain had already committed to that
model's answer, so one malformed reply ended the whole chain.

**Fix:** each agent's `validate` callback is passed into the chain and run on **every
attempt**. A failed shape check raises an internal `_ShapeValidationError`, which gets
the same immediate "try the next model" treatment as a rate limit. Only when every model
has failed, one way or another, does the call raise `NeedsDeepAnalysisError` or move to
the local tier. A bug inside a `validate` callback itself is deliberately *not* treated
as switch-worthy, so it still fails loudly. A follow-up widened switch-worthy errors to
provider/network failures (timeouts, 5xx, auth errors) and added a fifth model
(`gemini/gemini-3.8-flash`).

**Commits:** `bc5bfb8`, `936a1e2` (2026-09-24), `10c72ac`, `53a6b04` (2026-09-26).

**Regression tests:**
- `test_llm_fallback_validation.py`: `test_advances_past_a_network_successful_but_malformed_response`,
  `test_does_not_stop_at_the_first_malformed_response_even_without_a_prior_rate_limit`,
  `test_tries_every_model_in_the_chain_before_giving_up`,
  `test_falls_back_to_local_model_when_allow_local_and_every_cloud_model_is_malformed`,
  `test_a_bug_inside_validate_itself_is_not_treated_as_switch_worthy`,
  `test_a_non_rate_limit_non_shape_error_still_raises_immediately_without_trying_fallbacks`
- `test_llm_fallback_chain.py`: `test_a_shape_invalid_response_from_one_model_tries_the_next_model`,
  `test_shape_invalid_responses_from_every_model_raise_needs_deep_analysis`,
  `test_a_valid_first_response_never_tries_the_fallback_model_at_all`,
  `test_no_validate_callback_accepts_whatever_the_first_model_returns`

---

## 2. Overall confidence diluted toward zero

**Observed:** the headline "Overall confidence" was low on nearly every run, regardless
of how well-evidenced the analysis looked.

**Root cause:** the headline was computed by `confidence_node` right after search, over
**every** raw result from all five angles (30–50+), including deliberately broad angles
such as industry news and customer demand. Most of that pool was never cited by any
claim, but it all counted against the percentage.

**Fix:** `_confidence_dashboard` (which runs after every agent) now recomputes the
headline `agreeingSources` / `totalSources` / `percentage` / `label` over the sources
the claims actually **cite**, using the same relevance ≥ 0.5 bar. `perAngle` keeps the
raw-pool view. When nothing is cited the label reads "No cited sources yet" rather than
"0/0". Full method: [confidence-and-evidence-scoring-methodology.md](confidence-and-evidence-scoring-methodology.md).

**Commit:** `402dba6` (2026-09-24).

**Regression tests (`test_milestone3.py`):**
- `test_confidence_dashboard_recomputes_overall_percentage_from_cited_sources_not_the_raw_pool`
- `test_confidence_dashboard_overall_percentage_reflects_weak_cited_sources_too`
- `test_confidence_dashboard_labels_no_citations_honestly_rather_than_a_bare_0_0`

---

## 3. TAM/SAM/SOM computed but never shown; recency tile disappearing

**Observed:** reports never showed TAM/SAM/SOM figures, and the "Source recency" tile
sometimes vanished from the confidence dashboard.

**Root cause:** the backend had produced structured `tam` / `sam` / `som` claims since
2026-09-20 (`6a23374`), but `MarketOpportunity.jsx` never rendered them. Separately,
recency was drawn inside the average-relevance tile, so whenever average relevance was
unavailable, recency disappeared with it.

**Fix:** the Market tab renders a tile for each tier the sources support (unsupported
tiers, which are `null`, are left out rather than shown as blanks). Average relevance
and source recency now have separate tiles. The same commit replaced the four header nav
pills with the single account menu.

**Commit:** `ea9341a` (2026-09-24).

**Regression tests:**
- `MarketOpportunity.test.jsx`: "renders TAM/SAM/SOM tiers when the backend provides
  them", "omits the tier section entirely when none of TAM/SAM/SOM are supported by
  sources", "shows only the tiers that are actually supported, not all three"
- `ConfidenceDashboard.test.jsx`: recency rendered in its own tile
- `AccountMenu.test.jsx`: 7 tests for the new menu

---

## 4. Admin access lost on deploy, and data wiped by redeploys

**Observed:** an account could not reach Platform Health on the deployed app. There was
no shell or SQL console on Render's free tier to set `is_admin`, and once admin was
granted, a later deploy wiped it again along with every account and saved validation.

**Root causes (four, found in sequence):**
1. Promotion required a direct database `UPDATE`, which was unreachable on the host.
2. The first fix (`ADMIN_EMAILS` applied once at startup) ran **before** the matching
   account existed: the same deploy that set the variable also reset the on-disk SQLite
   database, so the account was re-created afterwards and never promoted.
3. The frontend read `isAdmin` only from `GET /auth/me` on initial page load, so even a
   promoted account didn't see the menu item until a full reload.
4. Underneath all of it, the backend was running on the **SQLite fallback**. The
   Postgres database was declared in `render.yaml` but had never been provisioned
   (no Blueprint sync), so `DATABASE_URL` was unset and every redeploy wiped the disk.
   Nothing reported this.

**Fixes:**
1. `ADMIN_EMAILS` env var, applied to existing accounts on every engine creation
   (`db._bootstrap_admin_emails`).
2. `auth.is_admin` also checks `ADMIN_EMAILS` on each lookup and self-promotes a
   matching account, so the order of deploy and sign-up no longer matters.
3. The app calls `GET /auth/me` immediately after sign-in.
4. The SQLite fallback now logs a warning on Render, `REQUIRE_PERSISTENT_DB=1` makes it
   a startup failure, and `GET /health` reports `"database": "postgresql" | "sqlite"`.
   The database was provisioned with a manual Blueprint sync (steps in
   [DEPLOYMENT.md](../DEPLOYMENT.md#database-postgresql-on-render)).

**Commits:** `9968bdc`, `e6b4d72`, `dfb0471` (2026-09-24), `1c92edc` (2026-09-26).

**Regression tests:**
- `test_admin_bootstrap.py`: `test_promotes_a_matching_existing_user_on_next_engine_creation`,
  `test_matches_case_insensitively_and_ignores_whitespace`,
  `test_does_nothing_when_the_env_var_is_unset`, `test_does_nothing_when_no_user_matches`
- `test_auth.py` (`IsAdminSelfHealTests`): `test_promotes_a_matching_account_on_first_lookup`,
  `test_matches_case_insensitively_and_ignores_whitespace`,
  `test_does_not_promote_a_non_matching_account`, `test_returns_false_for_an_unknown_user_id`
- `App.test.jsx`: "shows Platform health after signing in, without a page reload, once
  /auth/me confirms isAdmin"
- `test_db_persistence.py`: `test_backend_names_never_include_the_url`,
  `test_unset_and_blank_database_url_fall_back_to_sqlite`,
  `test_render_style_postgres_url_is_recognised`,
  `test_require_persistent_db_refuses_the_sqlite_fallback`,
  `test_sqlite_fallback_on_render_logs_a_warning`, `test_health_reports_the_database_backend`

**Still open:** Render's free Postgres expires 30 days after creation, which would cause
the same total data loss. See [Known Limitations §1.2](known-limitations-and-future-work.md#12-renders-free-postgresql-expires-after-30-days).

---

## 5. Summary

| # | Bug | Root cause in one line | Guarded by |
|---|---|---|---|
| 1 | Fallback chain skipped models | Shape check ran after the chain, not per attempt | 10 backend tests |
| 2 | Confidence diluted | Headline measured the raw search pool, not cited sources | 3 backend tests |
| 3 | TAM/SAM/SOM invisible | Backend field never rendered by the UI | 3 + frontend tests |
| 4 | Admin lost / data wiped | No shell for promotion, startup-only promotion, stale `isAdmin`, silent SQLite fallback | 14 backend + 1 frontend test |
