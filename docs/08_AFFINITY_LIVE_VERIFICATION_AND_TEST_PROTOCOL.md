# 08. Testing & Verification Documentation
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Verified & Operational  

---

## 📑 Document Table of Contents
- [1. Testing Methodology](#1-testing-methodology)
- [2. Live Cross-Industry Empirical Verification (7 Domains)](#2-live-cross-industry-empirical-verification-7-domains)
- [3. Forced Error-State & Partial Failure Isolation Suite](#3-forced-error-state--partial-failure-isolation-suite)
- [4. Anti-Hallucination & Factual Grounding Verification](#4-anti-hallucination--factual-grounding-verification)
- [5. Automated Regression Test Suite (`test_model_swap_fixes.py`)](#5-automated-regression-test-suite-test_model_swap_fixespy)

---

## 1. Testing Methodology

Affinity uses a dual-verification strategy combining **automated unit/regression test suites** with **live empirical system benchmarks** across distinct industry verticals.

---

## 2. Live Cross-Industry Empirical Verification (7 Domains)

All verification runs were executed against the live application (FastAPI backend on `:8000`, React frontend on `:5173`) using real search web data:

| # | Industry Domain | Submitted Idea | Verified System Output | Key Bug Discovered & Fixed |
|---|---|---|---|---|
| **1** | **Personal Finance** | Student Budgeting App | Extracted 4 real competitors: Bluevine, DailyBean, Rocket Money, TaxSlayer | Fixed line-join bug in scraped comparison tables (`046468f`) |
| **2** | **E-Commerce** | Coffee Subscription Box | Extracted specialty coffee brands: MistoBox, Onyx Coffee | Fixed spaCy false positive entity tagging (`cdbd60f`) |
| **3** | **Food Tech** | Meal-Prep Delivery | Extracted HelloFresh, Sprwt, Blue Apron, PeachDish | Verified multi-word entity preservation |
| **4** | **B2B SaaS** | Freelance Invoicing for Photographers | Extracted FreshBooks (placed in `low` price / `moderate` breadth grid) | Verified 3x3 positioning grid placement (`d33effc`) |
| **5** | **Fintech** | Bill Negotiation App | Filtered directory domain `competitors.app` | Excluded domain aggregators in `retrieval.py` (`a992076`) |
| **6** | **Health & Wellness** | Digital Gratitude Journal | Extracted Day One, Journey, Bloom | Enforced `_has_product_context()` for single-word entities |
| **7** | **Consumer Hardware** | Smart Water Bottle | Cross-Source Agreement rendered *"4/5 say market is growing"* | Verified `confidence.py` regex counts (`8334bdb`) |

---

## 3. Forced Error-State & Partial Failure Isolation Suite

### Test Execution Procedure
1. Set an invalid `GROQ_API_KEY=invalid_key_for_testing` in `backend/.env`.
2. Launched backend server on port 8001 (log captured in `backend/uvicorn-errorcheck.log`).
3. Executed validation requests via the React frontend.

### Results & Verification
- **HTTP Status:** `200 OK`
- **JSON Payload:** `marketOpportunity: null`, `errors.marketOpportunity` populated with friendly error string.
- **Competitors & Sources:** Extracted cleanly via local spaCy NER and returned in payload.
- **Frontend UI:** Rendered `UnavailableCard` on Market Opportunity tab while Competitors and Sources tabs rendered valid data.

---

## 4. Anti-Hallucination & Factual Grounding Verification

### Negative Constraint Evaluation
- **Test:** Submitted a niche startup concept with zero online TAM/SAM statistics (*"Handcrafted wooden keyboard caps for ergonomic mechanical keyboards"*).
- **Result:** Market Agent output: *"TAM/SAM figures are not clear from the provided sources."* Zero fake numbers generated.

### Invalid Escape Repair Test
- **Test:** Tested `qwen/qwen3.8-27b` output containing single backslash apostrophes (`don\'t`).
- **Result:** `_repair_invalid_escapes()` in `market_agent.py` stripped the illegal escape character, enabling `json.loads()` to parse the valid analysis cleanly.

---

## 5. Automated Test Suite

> **Correction:** an earlier draft of this section named a file
> (`backend/tests/test_model_swap_fixes.py`) and specific test functions/pass-rate
> ("16/16 passing") that don't exist — that file isn't in the repo (only a stale
> compiled `.pyc` remains, meaning it was deleted or renamed at some point without this
> doc being updated). The real coverage for escape-repair and model-fallback behavior
> lives in `backend/tests/test_milestone3.py` and `backend/agent/llm.py`'s own
> docstrings, under different test names than what was previously listed here.

Run the real suite from `backend/`:

```bash
python -m unittest discover -s tests
```

As of this writing: **51 tests passing** across `test_milestone2.py`,
`test_milestone3.py`, `test_async_email.py`, `test_report_assembler.py`, and
`test_integration.py` (unit, contract, async, and concurrency tests; the one
real-provider test in `test_integration.py` only runs when `GROQ_API_KEY` is set).
Escape-repair behavior specifically is covered by
`test_milestone3.py::test_structured_parser_repairs_invalid_escape_sequences`;
model-fallback switching is exercised through `agent/llm.py`'s
`kickoff_with_fallback()` in the mocked LLM tests across the same file.
