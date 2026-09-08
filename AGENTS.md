# AGENTS.md — Start Here

**Purpose of this file:** if you are an AI agent (or a human) picking up this repo
cold, read this first. It tells you what the project is, exactly what state it's in
right now, what's broken, what's not started, and where to pick up — without needing
to re-derive any of that from git history or code archaeology.

Last updated: Sept 6, 2026 · Branch: `staging` · Last commit: `c4c0752`

---

## 1. What this project is

**Affinity** — an AI startup-idea validator. A founder submits an idea + target
customer + problem statement; the backend runs a LangGraph pipeline that searches
the web, then produces a market-opportunity analysis, a competitor comparison, and
an opportunity score. React/Tailwind frontend, FastAPI backend.

Two internal audiences read this repo: a team of student engineers (see §7 for who
owns what) building it as an academic milestone project, and any AI agent asked to
continue the work. Read [`README.md`](README.md) for the user-facing pitch;
[`docs/architecture.md`](docs/architecture.md) for the full system design. This file
is the "what's actually true right now, and what do I do next" layer on top of both.

## 2. Current state in one paragraph

Milestone 1 and 2's core pipeline work. Market Opportunity is a real LLM agent
(Groq). Competitor Discovery was deliberately rewritten from an LLM agent to local
spaCy NER — no API call, by design, to keep the shared Groq quota free for Market
Opportunity. Partial-failure handling, error-state UI, and full node-boundary
logging all work and are verified live (not just unit-tested). Two real, open
problems remain (§3), one stretch feature was never started (§4), and one
deliverable (a teammate's validation report) has the underlying data but isn't
written up yet (§4).

## 3. Known bugs — read before touching related code

### 3a. Competitor name-quality bug — FIXED in `cdbd60f`
**Was:** `backend/agent/competitor_agent.py`'s NER extraction sometimes returned
garbage as competitor names — generic single words mislabeled as `ORG` by spaCy's
small model (`en_core_web_sm`), e.g. "History", "CBT", "Windows", "Reply",
"Newsweek". Found via live testing across 3 industries (fintech/health/hardware) —
see [`docs/milestone2-verification.md`](docs/milestone2-verification.md) and the
validation-plan PDF a teammate (Varshini) produced.

**Fix:** single-word, non-camelCase candidates now also require product-ish context
(price, subscription, "app", "alternative", etc.) nearby in at least one mention, on
top of the existing 2+-mentions bar — see `_has_product_context` and the updated
`_extract_entities` docstring in `competitor_agent.py`. camelCase and multi-word
names (HelloFresh, Rocket Money, Onyx) were never the source of this failure mode
and are untouched. Also expanded `_GENERIC_WORDS` for platform/UI-chrome words
(android, ios, pdf, reply, ai) and a couple of merge-artifact fragments.

**Verified:** live, across 7 ideas (the 3 that surfaced the bug + the 4 already-
confirmed-good ones) — every single-word false positive and merge-artifact phrase
from the original reports is gone, no previously-confirmed real competitor lost.

**Residual, out of scope:** occasional real-but-irrelevant companies still surface
(e.g. "Verizon" for a bill-negotiation idea) — that's the search/retrieval step
surfacing weakly-relevant sources, a different root cause (topical relevance, not
entity-extraction correctness) than this bug was. Don't conflate the two if you see
an odd name again — check whether it's a real company mentioned off-topic (retrieval
issue) vs. actual mislabeled text (would be a new instance of this bug class).

### 3b. Positioning grid doesn't render in live use (real, unfixed, MEDIUM priority)
**Symptom:** `frontend/src/components/CompetitorAnalysis.jsx`'s 3×3 positioning grid
(`PositioningGrid`) is correctly built and dimensioned, but since Competitor
Discovery moved to NER, `estimatedPrice`/`featureBreadth` are *always* `"unknown"`
in real responses (NER can't estimate those categories the way an LLM could). The
grid's `placed` filter requires both fields to be classified, so `placed.length` is
always 0 and the grid silently returns `null` — never visible to a real user.

**Where to start:** either (a) give Competitor Discovery a cheap heuristic for
these two fields (e.g. price signal from `$`-amount mentions in the snippet text,
breadth from feature-keyword density) so it's not always `"unknown"`, or (b) accept
the grid is dead code under the current design and remove it / replace it with
something NER can actually support, or (c) leave it and document it as a known
limitation for submission. This is a product decision as much as a coding one —
surface it to the team rather than picking silently.

## 4. Not started / not finished

- **Confidence Indicator** (cross-source agreement, e.g. "3 of 5 sources agree on
  market growth") — a planned stretch feature, zero code exists (`grep` for
  `confidence` in `backend/` turns up nothing). Assigned to Sashi, zero blockers to
  starting. Don't confuse this with the frontend's existing "Confidence" badge in
  `ValidationResults.jsx` — that's a different metric (average search-relevance
  score), not source agreement.
- **`docs/milestone2-validation.md`** — the actual cross-industry validation report
  doesn't exist yet. The data for it does (3 ideas tested live: fintech, health &
  wellness, consumer hardware — see the verification doc and Varshini's plan PDF).
  Someone needs to transcribe those results into the report template that PDF
  contains and save it as `docs/milestone2-validation.md`. If you're an agent asked
  to "finish the validation report," this is the concrete deliverable — the
  underlying test data is not the report itself.
- **B2/B3 deliberate breaking-tests** (force each pipeline node to fail one at a
  time, confirm 200 + partial data + correct frontend state for each) — the
  *capability* is verified (see `docs/milestone2-verification.md` §2), but the full
  three-node breaking-test matrix a teammate planned was never completed as a
  dedicated pass. Low priority — the underlying mechanism works, this is closing out
  a checklist, not fixing something broken.

## 5. Traps for whoever works on this next

These cost real time this session — don't rediscover them the hard way.

- **The backend has no auto-reload.** It's normally started as
  `uvicorn main:app --host 127.0.0.1 --port 8000` (no `--reload`). Editing
  `backend/` code does nothing to a running server — you must kill the process and
  restart it, or your test results will silently reflect stale code. Find it with
  `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` and filter for
  `uvicorn` in the command line (PowerShell), then `Stop-Process -Force`.
- **Logging was silently broken until `c4c0752`.** `main.py` didn't call
  `logging.basicConfig()`, so every `logger.info()` in `agent/graph.py` went
  nowhere. If you're on a commit before that and things seem to "not log," this is
  why — pull latest or add `logging.basicConfig(level=logging.INFO)` yourself.
- **The frontend persists results in `sessionStorage`** (`App.jsx`,
  `affinity:lastValidation`). When testing a fix live in a browser, a stale
  pre-fix result can render even after a backend restart. Clear it
  (`sessionStorage.clear()` in devtools/`javascript_tool`) and reload before
  trusting what the UI shows.
- **The backend also caches identical requests** for 30 minutes in memory
  (`main.py`, keyed on normalized idea/targetCustomer/problem), but only caches
  responses with no `errors` set — so a cached response is never a masked failure,
  only ever a genuine past success. Doesn't explain stale-looking results after a
  *code* change though (see the two points above for that).
- **NER output is non-deterministic across runs** because it depends on live search
  results, which vary run to run even for the same idea. Don't treat a single test
  run (good or bad) as proof of a fix — this is exactly how the "CostCost"/"Ratings"
  false positives and the real "History"/"CBT" bug (§3a) were found: by testing
  multiple times across multiple ideas, not once.
- **Groq quota is real and shared** across the whole team on one free-tier key.
  The `reasoning_effort` fix (`backend/agent/llm.py`'s `_REASONING_EFFORT` map) is
  the actual fix for most exhaustion symptoms — don't re-diagnose this as "just add
  more retries" without checking that map first. Each model in the fallback chain
  needs its own confirmed-valid value (`"none"` vs `"low"` — they're not
  interchangeable across models, confirmed by direct testing).
- **A PDF that reads as "password-protected" to the `Read` tool may just need a
  second attempt** — one such false-positive happened this session on a genuinely
  unprotected file.

## 6. How to run it locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # required for Competitor Discovery
cp .env.example .env   # fill in GROQ_API_KEY; TAVILY_API_KEY optional
uvicorn main:app --host 127.0.0.1 --port 8000   # no --reload configured

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev   # http://localhost:5173
```

No test suite exists yet (`grep` for `test_*.py` under `backend/` turns up nothing)
— verification in this project has been live, manual testing against the running
app, documented in `docs/milestone2-verification.md`, not automated tests. If you
add one, it'd be a genuinely new capability, not filling in something broken.

## 7. Who owns what (for context, not permission)

| Person | Owns |
|---|---|
| Yasaswini | Market Opportunity Agent, Competitor Discovery Agent, most backend fixes this session |
| Yalene | Orchestration / partial-failure wiring |
| Sashi | Opportunity Score (done), Confidence Indicator (not started) |
| Anu Kumari | Frontend components (null-state UI, positioning grid UI) |
| Varshini | Cross-industry validation testing/report |

This is informational, not a permission gate — if you're an agent asked to fix §3a,
fix it regardless of whose name is on this list. It's here so you understand *why*
a given piece of code looks the way it does, and who to (conceptually) flag a
finding to if the request is "investigate, don't fix."

## 8. Where to go deeper

- [`docs/architecture.md`](docs/architecture.md) — full system design, data flow,
  API contract, tech-stack rationale (the "why," not just the "what")
- [`docs/milestone2-status.md`](docs/milestone2-status.md) — task-by-task status,
  who's blocked on what
- [`docs/milestone2-verification.md`](docs/milestone2-verification.md) — actual
  checks run against the live app, with method + result for each
- [`docs/milestone2-plan.md`](docs/milestone2-plan.md) — the original plan
  (historical intent — not updated to match final implementation, architecture.md
  and this file are the current-state sources of truth)
- [`backend/README.md`](backend/README.md) — backend-specific file-by-file guide
