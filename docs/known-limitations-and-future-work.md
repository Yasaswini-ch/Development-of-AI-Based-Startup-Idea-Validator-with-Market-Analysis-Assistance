# Known Limitations & Future Work

**Version:** 1.1 · 2026-09-26 (written against the `staging` branch; §7 added after the five-pillar Sprints 1–4)  
**Audience:** Examiners, future maintainers, the team  

This is an honest list of what Affinity does not do yet, or does with a known
compromise. Each item says what the limitation is, why it exists, how much it matters,
and what fixing it would take. Items are verified against the code on the date above.

---

## 1. Data retention and hosting

### 1.1 Saved validations expire after 7 days, even for signed-in users
- **What:** `session_store.py` prunes every session 7 days after its last update, and
  keeps at most 200 sessions across **all** users (oldest dropped first). An account is
  permanent, but its History, Dashboard and Compare data only cover sessions that are
  still inside that window.
- **Why:** sessions were designed as a bounded cache before accounts existed. Keeping
  owned sessions forever is a real storage/cost decision, not just an auth change.
- **Impact:** a founder returning after a week finds an empty board. With more than 200
  runs platform-wide, the oldest disappear sooner.
- **Fix:** exempt sessions with a `user_id` from the TTL (or give them a much longer
  one) and cap per user instead of globally. Until then, founders should export a PDF
  of anything they want to keep.

### 1.2 Render's free PostgreSQL expires after 30 days
- **What:** free-plan databases on Render expire 30 days after creation; after a short
  grace period the database and all data are deleted.
- **Impact:** every account, saved validation, admin flag and event log row is lost at
  once. This can hit in the middle of a demo or defense.
- **Mitigation today:** track the creation date; upgrade or recreate ahead of time;
  `REQUIRE_PERSISTENT_DB=1` and `GET /health` make a missing database visible. See
  [DEPLOYMENT.md](../DEPLOYMENT.md#free-tier-expiry-30-days).
- **Fix:** a paid database plan, or another managed Postgres with a free tier that
  doesn't expire.

### 1.3 No migration tooling
- **What:** schema changes rely on `create_all()` plus a small hand-written
  `_migrate_missing_columns` helper that only adds missing columns.
- **Fix:** adopt Alembic before the schema changes again.

## 2. Accounts and security

### 2.1 No password reset and no email verification
- **What:** there is no "forgot password" flow and no check that the email belongs to
  the person signing up.
- **Impact:** a user who forgets their password must create a new account. Anyone can
  register any email address, including one listed in `ADMIN_EMAILS` if that account
  doesn't exist yet (see 2.3).
- **Fix:** a short-lived, single-use reset token emailed through the existing SendGrid
  path, plus a verification link at sign-up.

### 2.2 No token revocation
- **What:** JWTs are stateless and valid for 30 days. Signing out only clears the
  browser copy. There is no "sign out everywhere".
- **Fix:** a revocation list or short-lived access tokens with refresh tokens.
  Rotating `AUTH_SECRET_KEY` is the only global kill switch today.

### 2.3 `ADMIN_EMAILS` trusts the email string
- **What:** because emails aren't verified, if an address in `ADMIN_EMAILS` has not
  signed up yet, whoever registers it first becomes an admin. Admin access is read-only
  platform metrics, so the blast radius is limited.
- **Mitigation:** sign up with the admin address **before** adding it to
  `ADMIN_EMAILS`. Removing an address from the list does not demote an existing admin;
  that needs SQL.
- **Fix:** email verification (2.1).

### 2.4 Session links are capability links
- **What:** report, chat, PDF and compare endpoints accept any valid session id without
  an ownership check, so anyone holding a link can open that report. This is deliberate
  (emailed links must work without sign-in) but worth stating.
- **Fix, if needed:** optional per-session privacy that requires the owner's token.

### 2.5 No team workspaces or roles beyond admin
One account = one founder's own board. Sharing ideas inside a team, incubator or class
is not supported.

## 3. AI pipeline

### 3.1 The local-model fallback needs real hardware
- **What:** the last-resort tier runs `ollama/qwen2.5:7b` through Ollama at
  `OLLAMA_BASE_URL` (default `localhost:11434`). Render's free tier has no GPU and no
  Ollama server, so on the deployed app this tier is skipped (`local_llm_available()`
  returns false): after a second cloud pass the request drops to the deterministic,
  `degraded: true` result.
- **Impact:** when every cloud model is exhausted, deployed users get the weaker
  fallback rather than a slow but full AI result. On a laptop with Ollama and a capable
  GPU the tier works, but can take minutes per call (240 s timeout).
- **Fix:** host Ollama on a GPU machine and point `OLLAMA_BASE_URL` at it, or add a paid
  cloud model as the final tier.

### 3.2 Free-tier LLM quotas are shared
All users share the same Groq and Gemini free-tier quotas. The five-model fallback chain
spreads load across separate quota buckets, but heavy use can still exhaust all of them
at once. More backend instances do not add quota.

### 3.3 Confidence measures relevance, not truth
See [confidence-and-evidence-scoring-methodology.md](confidence-and-evidence-scoring-methodology.md) §7.
A relevant source can still be wrong, and the 0.5 threshold is an uncalibrated
heuristic.

### 3.4 Competitor detection and confidence scoring (review feedback)
Competitors come only from spaCy NER over a few search snippets (capped at 4), and fewer
competitors found raises the Opportunity Score. Confidence measures source relevance,
not agreement. Options and a recommended plan are in
[competitor-detection-and-confidence-scoring-proposal.md](competitor-detection-and-confidence-scoring-proposal.md).

### 3.5 Market figures depend on what search returns
TAM/SAM/SOM tiers are `null` whenever the retrieved snippets don't state them, which is
common for niche ideas. That's the intended behaviour (no guessing), but it means many
reports show only a narrative market size.

## 4. Analytics

- **"Avg pipeline latency" on Platform Health is a per-node average**, not end-to-end
  time per validation. See [doc 22 §8](22_AFFINITY_MILESTONE_5_ANALYTICS_DASHBOARDS_AND_ACCESS_CONTROL.md#8-known-caveats).
- **API and node success rates reset on restart**, because they come from in-process
  counters rather than the durable event log.
- **No live provider quota view.** Nothing observes real rate-limit headers, so it is
  deliberately not shown.

## 5. Documentation: two overlapping doc sets (process lesson)

- **What:** `docs/` holds two sets that describe the same system:
  - the numbered set `01_AFFINITY_*.md` … `22_AFFINITY_*.md`, written as a formal
    report/thesis structure, and
  - the lowercase set (`architecture.md`, `api-reference.md`, `frontend-spec.md`,
    `prompt-engineering-agent-design.md`, `security-privacy-ethics.md`, ...), which is
    what engineers updated alongside code changes.
- **What went wrong:** features changed faster than both sets were updated. The
  numbered docs 19–21 at one point said auth and the comparison matrix didn't exist
  after both had shipped, and several numbered docs still described the pre-Milestone-4
  API. The lowercase set was generally more accurate because it was edited in the same
  commits as the code.
- **Status (2026-09-26):** both sets were reconciled against the code in one pass, and
  the docs index ([`docs/README.md`](README.md)) now maps each numbered doc to its
  lowercase counterpart. Both sets still exist, so the risk of drift remains.
- **Lesson:** keep one source of truth per topic. Either retire the overlapping
  numbered docs in favour of the lowercase ones, or turn the numbered docs into short
  summaries that link to the lowercase ones. A decision on which is still open.
- **Rule of thumb until then:** when code changes behaviour, update the lowercase doc in
  the same commit, and grep the numbered set for the old claim.

## 6. Planned but not built

From the original roadmap ([doc 17](17_AFFINITY_MILESTONE_3_4_TECHNICAL_ROADMAP.md)):
pitch-deck outline export, custom search-angle toggles, monthly competitor-movement
alerts and webhooks, an incubator API portal with API keys, GitHub SSO. (Google sign-in
was built in Sprint 4; see §7.4.)

## 7. Five-pillar features

Details and formulas: [doc 23](23_AFFINITY_FIVE_PILLAR_EVIDENCE_STRATEGY_AND_GOOGLE_SSO.md).

### 7.1 Email and comparisons don't include the new sections
- **What:** the PDF dossier now includes Voice-of-Market quotes, the Viability Index,
  wedge blueprints, the delivery roadmap and commercial economics, but the report email
  (`email_delivery.py`) still renders only the pre-sprint sections. Compare Ideas and the
  Dashboard also ignore them.
- **Impact:** low to medium. A founder who shares the email instead of the PDF loses the
  most decision-ready parts.
- **Fix:** add the sections to the email builder; add `viabilityIndex.compositeScore`
  to the compare view.

### 7.2 Economics and roadmap are templates, not forecasts
- **What:** ARPU is one of three values ($19/$45/$99), CAC is a multiple of ARPU scaled
  by GTM channel fit, pricing-tier features and the three-person team are fixed, and the
  exit-gate targets are the same for every idea.
- **Why:** deliberate. These are computed from signals the pipeline already has instead
  of asking a model to invent numbers.
- **Impact:** medium. Two different ideas in the same price band get near-identical
  pricing tables. The UI does not currently label these blocks as estimates.

### 7.3 Provenance badges cover only some claims
- **What:** the Grounded/Inferred badge is shown on the market-size sentence and the
  five Viability Index axes. Trends, segments, SWOT, MVP and GTM claims still use the
  citation popover only, and the wedge conviction % uses its own colour scale.
- **Fix:** render `ProvenanceBadge` wherever a claim has `sourceIds`.

### 7.4 Google sign-in edge cases
- **Account matching is by email.** A Google sign-in takes over a local account with the
  same email (marks it `google`; the password still works). No unlinking.
- **A Google-only account can't add a password** (sign-up says the email already exists,
  and the password form fails closed).
- **Old SQLite files** keep `password_hash NOT NULL`, so a first Google sign-in into one
  fails until the file is recreated. Postgres is migrated automatically.
- The Google profile photo (`avatarUrl`) is shown in the account menu; local accounts
  show their initial instead.

### 7.5 Heuristic text extraction
- Voice-of-Market quotes are tagged by keyword. A sentence containing "manual" or
  "problem" can be tagged *Observed Friction* without being a customer complaint.
- The wedge's "Incumbent Blindspot" always uses the **first** listed competitor, which
  is the first one NER found, not necessarily the closest one. In quick mode (no
  profiling) there are no weaknesses, so that vector is always inferred and conviction
  tops out at 75%.

