"""Deterministic Report Assembler (Milestone 4, Track D).

Assembles the canonical report object described in
docs/unique-features-plan.md §6 from a validation session's already-
computed context (see session_store.create_session). Per the shared
artifact mesh rules in that doc: this node only synthesizes existing
artifacts, it never re-derives analysis or calls an LLM/search provider.

contradictions/experiments/actionPlan are Tracks B/C, built separately by
other agents (agent/contradiction_detector.py, agent/experiment_generator.py,
agent/action_plan.py) and not yet wired into the pipeline as of this
module's creation - they default to empty here and will populate
automatically the moment main.py's session context starts carrying them,
no change needed in this file when that lands.
"""

import uuid
from datetime import datetime, timezone

_ARTIFACT_SECTIONS = ("marketOpportunity", "competitors", "whiteSpace", "swot", "mvp", "gtm")


def _section_errors(context: dict) -> dict:
    """A section is only ever None in session context if its own pipeline
    node failed outright (see graph.py's per-node try/except) - a
    successful-but-degraded (deterministic fallback) result is still a
    real dict with "degraded": true, not None. session_store doesn't
    persist the original error *message* (main.py never stored
    state["errors"]), so this reports which sections are missing, not why -
    a real message here is a Track F/session_store follow-up, not invented
    here.
    """
    return {
        section: "This section was not available for this validation run."
        for section in _ARTIFACT_SECTIONS
        if context.get(section) is None
    }


def _degraded_sections(context: dict) -> list[str]:
    return [
        section
        for section in _ARTIFACT_SECTIONS
        if isinstance(context.get(section), dict) and context[section].get("degraded")
    ]


def assemble_report(session_id: str, context: dict) -> dict:
    """Build the canonical report object for one validation session.

    `context` is exactly session_store's stored context dict (idea,
    targetCustomer, problem, summary, sources, confidence,
    marketOpportunity, competitors, whiteSpace, swot, mvp, gtm, and -
    once Tracks B/C land - contradictions/experiments/actionPlan).
    """
    market_opportunity = context.get("marketOpportunity") or {}

    return {
        "reportId": str(uuid.uuid4()),
        "sessionId": session_id,
        "ideaSummary": {
            "idea": context.get("idea", ""),
            "targetCustomer": context.get("targetCustomer", ""),
            "problem": context.get("problem", ""),
            "summary": context.get("summary", ""),
        },
        "marketOpportunity": context.get("marketOpportunity"),
        "competitors": context.get("competitors"),
        "opportunityScore": market_opportunity.get("opportunityScore", 0),
        "swot": context.get("swot"),
        "mvp": context.get("mvp"),
        "gtm": context.get("gtm"),
        "confidence": context.get("confidence"),
        # Tracks B/C - default empty until contradiction_detector.py /
        # experiment_generator.py / action_plan.py are wired into the
        # pipeline and their output starts flowing into session context.
        "contradictions": context.get("contradictions") or [],
        "experiments": context.get("experiments") or [],
        "actionPlan": context.get("actionPlan"),
        "sources": context.get("sources") or [],
        "sectionErrors": _section_errors(context),
        "degradedSections": _degraded_sections(context),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def report_to_pdf_input(report: dict) -> dict:
    """Adapt the canonical report's nested shape back to the flat dict
    pdf_exporter.generate_dossier_pdf() actually reads (idea,
    targetCustomer, marketOpportunity, summary, competitors, swot, ...) -
    the same flat shape session_store's context already uses for the two
    existing PDF export routes. A shim here, rather than changing
    pdf_exporter.py itself, keeps those two existing call sites (which
    already pass the flat shape directly) untouched.
    """
    idea_summary = report.get("ideaSummary") or {}
    return {
        "idea": idea_summary.get("idea", ""),
        "targetCustomer": idea_summary.get("targetCustomer", ""),
        "problem": idea_summary.get("problem", ""),
        "summary": idea_summary.get("summary", ""),
        "marketOpportunity": report.get("marketOpportunity"),
        "competitors": report.get("competitors"),
        "swot": report.get("swot"),
        "mvp": report.get("mvp"),
        "gtm": report.get("gtm"),
    }
