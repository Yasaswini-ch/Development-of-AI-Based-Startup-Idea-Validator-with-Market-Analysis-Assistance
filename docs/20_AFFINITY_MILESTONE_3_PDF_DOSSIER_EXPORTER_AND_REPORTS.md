# 20. Milestone 3: PDF Dossier Exporter

**Document Version:** 2.0 (corrected — see note below)
**Status:** Implemented & Operational
**Target Audience:** Backend Engineers, Frontend Engineers

---

> **Correction from earlier drafts of this document:** a previous version described
> `/api/v1/validations/{id}/export-pdf`-style endpoints with `Authorization: Bearer`
> tokens, `?theme=dark|light&branding=true` query params, a Playwright/headless-Chromium
> rendering option, and a code sample that didn't match the real module. None of that
> exists — there is no authentication anywhere in this app, no theme/branding query
> params, no Playwright dependency, and the actual `generate_dossier_pdf()` function
> looks nothing like what was shown. This version describes the real
> `backend/agent/pdf_exporter.py` and its two real endpoints.

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

Neither endpoint requires an access token or any auth header — this app has no
authentication layer at all (see doc 19's corrected version). Both are rate-limited
per IP (`EXPORT_PDF_RATE_LIMIT_PER_MINUTE`, default 10/minute) rather than gated by a
token.

A third, Milestone 4 endpoint also produces a PDF as a side effect: `POST
/reports/{sessionId}/email` assembles the canonical report
(`agent/report_assembler.py`), renders it through the same `pdf_exporter.py`, and
emails it as an attachment via Resend rather than returning it directly.

## 2. What the Generated PDF Actually Contains

Four sections, built directly from whatever fields are present in the input dict
(every field access is defensive — a missing section is simply skipped, not an error):

1. **Header + Executive Summary** — idea title, target customer, the opportunity
   score (read from `marketOpportunity.opportunityScore`), and the `summary` string.
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
