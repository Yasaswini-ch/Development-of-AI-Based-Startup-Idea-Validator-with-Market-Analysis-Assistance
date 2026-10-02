# 20. Milestone 3: PDF Dossier Exporter

**Document Version:** 2.1 (updated 2026-09-26 — see notes below)
**Status:** Implemented & Operational
**Target Audience:** Backend Engineers, Frontend Engineers

---

> **Correction from earlier drafts of this document:** a previous version described
> `/api/v1/validations/{id}/export-pdf`-style endpoints with `Authorization: Bearer`
> tokens, `?theme=dark|light&branding=true` query params, a Playwright/headless-Chromium
> rendering option, and a code sample that didn't match the real module. None of that
> exists: the PDF endpoints take no auth header, there are no theme/branding query
> params, no Playwright dependency, and the actual `generate_dossier_pdf()` function
> looks nothing like what was shown. This version describes the real
> `backend/agent/pdf_exporter.py` and its two real endpoints.
>
> **Update 2026-09-26:** version 2 of this note also said "there is no authentication
> anywhere in this app". That is no longer true. The app now has optional JWT accounts
> and an admin role (see [doc 19](19_AFFINITY_MILESTONE_3_POSTGRESQL_AUTH_AND_DATA_PERSISTENCE.md)).
> The PDF endpoints themselves still don't require a token, as described below.

## 1. What Actually Exists

**Renderer:** ReportLab only (`SimpleDocTemplate` + `Platypus` flowables — `Paragraph`,
`Table`, `Spacer`, `HRFlowable`). No Playwright, no headless browser, no HTML-to-PDF
step anywhere in this pipeline.

**Two real endpoints** (`backend/main.py`):

```
POST /export-pdf
  Body: a validated response-shaped JSON object (PdfExportRequest schema - idea,
        targetCustomer, marketOpportunity, competitors, swot, mvp, gtm, etc., all
        optional, extra fields allowed so a full /validate response body can be
        passed straight through)
  -> 200, application/pdf, Content-Disposition: attachment; filename="Affinity_Validation_Report.pdf"

GET /validate/{sessionId}/pdf
  -> Loads that session's already-stored context (session_store.py) and renders the
     same way - no request body needed, no re-running the pipeline.
  -> 200, application/pdf, Content-Disposition: attachment; filename="Affinity_Report_{sessionId}.pdf"
```

Neither endpoint requires an access token. The app does have optional JWT accounts
(see doc 19 §4), but PDF export deliberately stays open: the session id is a random
UUID that works as a capability link, so a report link emailed to a founder downloads
without signing in. The flip side is that anyone holding a session id can download
that report. Both endpoints are rate-limited per IP (`EXPORT_PDF_RATE_LIMIT_PER_MINUTE`,
default 10/minute).

> **Correction:** `POST /reports/{sessionId}/email` no longer renders a PDF at all -
> it assembles the canonical report (`agent/report_assembler.py`) and emails its
> HTML/text bodies directly via SendGrid, with no attachment. The HTML/text bodies
> already carry the full report content on their own; a PDF is still available, just
> via a separate, direct-download path (`GET /validate/{sessionId}/pdf`, covered
> below) rather than bundled into every email.

## 2. What the Generated PDF Contains (updated 2026-10-03)

> **Correction.** Earlier versions of this chapter said the PDF had four sections and no
> charts. That was wrong or out of date: the exporter has drawn charts since Milestone 4,
> and as of 2026-10-03 it prints everything the on-screen report shows. A real report is
> typically 15 to 25 pages.

Every field is read defensively: a missing section is skipped, not an error. Numbered
sections (`§01`, `§02`, ...) are only numbered when present.

**Front matter**
- Cover and idea context (idea, target customer, problem) and the **verdict card**: decision,
  headline score, reasons and next step.
- **Executive summary and KPI strip** (sources, competitors, gaps, personas).
- **Evidence confidence**: overall score and bars for source coverage, cross-source agreement,
  direct evidence, average relevance and dated sources.
- **Source agreement by research angle** and **Sources by research angle** (bar charts).
- **About this report**: a box listing every section built by a rule-based fallback, every
  section that failed, competitors profiled from search text only, and any SAM or SOM that is a
  labelled estimate. Present only when there is something to say.

**Analysis sections**
1. **Market size and growth**: the sized market, CAGR, opportunity score; **TAM / SAM / SOM cards**
   each marked Sourced or Estimate (an estimate shows its assumption); **market trends** with
   Grounded or Inferred tags; **customer segments** with pain points, motivations and buying
   behaviour.
2. **Competitor landscape**: type, pricing and breadth table; weaknesses of direct rivals; a
   **positioning chart** (price by feature breadth); **competitor profiles** (offering, pricing,
   business model, rating or founding year, strengths, weaknesses, where the idea can differ);
   **How your idea compares** (the idea against up to 8 rivals, three to a table); and **similar
   products** from Product Hunt.
3. **SWOT and risk matrix**: four quadrants with provenance tags, a **risk heat-map**, a risks
   table with mitigations, and the **bear case** (investor objections with suggested answers).
4. **Tension flags** (contradictions), **voice of the market** (customer and owner quotes),
   **market viability** (a **radar chart** and scored axes), **market white space**, **strategic
   wedges**.
5. **MVP feature plan** (impact and effort), **delivery roadmap** (a **timeline chart**),
   **key assumptions**, **validation experiments**, **commercial economics**, **go-to-market**,
   **revenue model options** and the **90-day action plan**. The roadmap, economics and experiments
   sections carry an Estimate badge.

**Appendix**
- **Cited sources**: the most load-bearing sources.
- **Evidence log**: every retrieved source, in citation order (`src-1`, `src-2`, ...), with its
  research angle, relevance, date and an excerpt. Capped at 120 sources; the count beyond that is
  stated.

**Limits.** URLs are printed as text, not clickable links. A very long source list or comparison
table adds pages. Rows that cannot be split across pages are kept short on purpose, so long text
is clipped with an ellipsis (the full text is in the on-screen report).

## 3. Real Code (verbatim structure, `backend/agent/pdf_exporter.py`)

```python
def generate_dossier_pdf(dossier_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, ...)
    story = []

    idea_title = dossier_data.get("idea", dossier_data.get("ideaTitle", "Startup Concept"))
    story.append(Paragraph(f"Affinity Market Feasibility Dossier: {idea_title}", title_style))

    market_opp = dossier_data.get("marketOpportunity") or {}
    opp_score = market_opp.get("opportunityScore", ...)
    story.append(Paragraph(f"Feasibility Opportunity Score: {opp_score} / 100", body_style))
    # ... market size, segments table, competitor table, SWOT summary ...

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
```

## 4. Known Gap (documented honestly, not invented)

`generate_dossier_pdf()` expects a **flat** dict (`idea`, `targetCustomer`,
`marketOpportunity`, `summary`, `competitors`, `swot`, ...). The Milestone 4 canonical
report object (`report_assembler.py`) nests these under `ideaSummary` instead. Rather
than changing `pdf_exporter.py` itself (which would touch its two already-working call
sites above), `report_assembler.report_to_pdf_input()` adapts the canonical shape back
to the flat one before it reaches the exporter — a shim, not a rewrite.
