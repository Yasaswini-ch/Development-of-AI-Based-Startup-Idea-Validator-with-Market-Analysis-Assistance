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

## 2. What the Generated PDF Actually Contains

Four sections, built directly from whatever fields are present in the input dict
(every field access is defensive — a missing section is simply skipped, not an error):

1. **Header + Executive Summary** — idea title, target customer, the opportunity
   score (read from `marketOpportunity.opportunityScore`), the go/no-go `verdict` and
   its next step when present, and the `summary` string.
2. **Market Size & Growth** — `marketOpportunity.marketSize` and a table of up to 3
   customer segments (`segment`, `painPoints`).
3. **Competitor Landscape** — a table of up to 5 competitors with `name`,
   `estimatedPrice`, `featureBreadth` — these are frequently `"unknown"` in real
   output (see doc on competitor discovery), which the table renders as-is rather than
   hiding.
4. **SWOT & Risk Matrix** — strengths and weaknesses joined into two summary lines.
   SWOT items are `{"text": ..., "sourceIds": [...]}` objects (Milestone 4, Track A);
   the exporter reads `.get("text")` from each rather than assuming a bare string.

There is **no rendered opportunity-score gauge graphic, no rendered 3×3 competitor
positioning chart, and no source-citation index with hyperlinks** in the actual PDF —
those were described in the earlier, incorrect version of this document but were
never built. The competitor/segment data appears as plain tables, not visual charts.

MVP recommendations and GTM strategy are part of the canonical report object
(`report_assembler.py`, Milestone 4) but are not yet rendered into the PDF output
itself — `generate_dossier_pdf()` only reads the four sections listed above.

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
