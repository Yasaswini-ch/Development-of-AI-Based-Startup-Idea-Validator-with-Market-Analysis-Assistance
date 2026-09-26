"""
Automated PDF Report Exporter for Milestone 3.

Compiles validation dossiers into multi-page, executive publication-ready PDF documents
using ReportLab.
"""

import io
import logging
from typing import Any, Dict
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)


def generate_dossier_pdf(dossier_data: Dict[str, Any]) -> bytes:
    """Generate a publication-ready PDF binary stream for a validation dossier."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    # Custom Styles
    primary_color = colors.HexColor("#0F172A")
    accent_color = colors.HexColor("#2563EB")
    muted_color = colors.HexColor("#64748B")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=muted_color,
        spaceAfter=12,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=accent_color,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )

    # 1. Header Section
    idea_title = dossier_data.get("idea", dossier_data.get("ideaTitle", "Startup Concept"))
    story.append(Paragraph(f"Affinity Market Feasibility Dossier: {idea_title}", title_style))
    story.append(Paragraph(f"Target Customer: {dossier_data.get('targetCustomer', 'General Market')} | Generated via Affinity Engine", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=12))

    # 2. Score & Executive Summary
    market_opp = dossier_data.get("marketOpportunity") or {}
    opp_score = market_opp.get("opportunityScore", dossier_data.get("opportunityScore", {}).get("score", "N/A"))
    
    summary_text = dossier_data.get("summary", "Automated feasibility evaluation compiled from live web search retrieval.")
    verdict = dossier_data.get("verdict") or {}
    story.append(Paragraph("1. Verdict & Executive Summary", section_heading))
    # Same hierarchy as the on-screen report: the verdict's score is the one
    # headline number, the opportunity score is a labelled secondary metric.
    if isinstance(verdict.get("score"), (int, float)):
        score_name = escape(str(verdict.get("scoreName") or "Score"))
        story.append(Paragraph(f"<b>{score_name}:</b> {verdict['score']} / 100", body_style))
        if opp_score not in (None, "N/A", 0):
            story.append(Paragraph(f"Opportunity score (secondary): {opp_score} / 100", body_style))
    else:
        story.append(Paragraph(f"<b>Feasibility Opportunity Score:</b> {opp_score} / 100", body_style))
    if verdict.get("label"):
        story.append(Paragraph(
            f"<b>Verdict: {escape(verdict['label'])}.</b> {escape(verdict.get('headline', ''))}",
            body_style,
        ))
        if verdict.get("nextStep"):
            story.append(Paragraph(f"<b>Next step:</b> {escape(verdict['nextStep'])}", body_style))
    story.append(Paragraph(f"<b>Executive Summary:</b> {summary_text}", body_style))
    story.append(Spacer(1, 8))

    # 3. Market Opportunity Details
    if market_opp:
        story.append(Paragraph("2. Market Size & Growth Dynamics", section_heading))
        m_size = market_opp.get("marketSize", "Emerging Sector")
        cagr = market_opp.get("cagr", "N/A")
        story.append(Paragraph(f"<b>Estimated TAM/SAM Market Size:</b> {m_size}", body_style))
        story.append(Paragraph(f"<b>Compound Annual Growth Rate (CAGR):</b> {cagr}", body_style))

        segments = market_opp.get("segments") or []
        if segments:
            table_data = [["Customer Segment", "Pain Points / Needs"]]
            for seg in segments[:3]:
                table_data.append([
                    Paragraph(f"<b>{seg.get('segment', '')}</b>", body_style),
                    Paragraph(seg.get('painPoints', ''), body_style),
                ])
            t = Table(table_data, colWidths=[180, 340])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))

    # 4. Competitor Analysis Table
    competitors_data = dossier_data.get("competitors") or {}
    comp_list = competitors_data.get("competitors") or []
    if comp_list:
        story.append(Paragraph("3. Competitor Landscape & Positioning", section_heading))
        # Profiled competitors (competitor_agent._profile_with_llm) carry a
        # stated pricing note and weaknesses; NER-only ones fall back to
        # the rough price bucket and feature breadth.
        profiled = bool(competitors_data.get("profiled"))
        if profiled:
            c_table_data = [["Competitor", "Type", "Pricing", "Key weakness"]]
        else:
            c_table_data = [["Competitor Name", "Pricing Tier", "Feature Breadth"]]
        for c in comp_list[:5]:
            if profiled:
                weaknesses = c.get("weaknesses") or []
                c_table_data.append([
                    Paragraph(f"<b>{escape(c.get('name', ''))}</b>", body_style),
                    Paragraph(escape(c.get("classification", "unknown")), body_style),
                    Paragraph(escape(c.get("pricing") or c.get("estimatedPrice", "unknown")), body_style),
                    Paragraph(escape(weaknesses[0] if weaknesses else "unknown"), body_style),
                ])
            else:
                c_table_data.append([
                    Paragraph(f"<b>{c.get('name', '')}</b>", body_style),
                    Paragraph(c.get('priceBucket', c.get('estimatedPrice', 'unknown')), body_style),
                    Paragraph(c.get('featureBreadth', 'unknown'), body_style),
                ])
        ct = Table(c_table_data, colWidths=[130, 70, 130, 190] if profiled else [200, 160, 160])
        ct.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ('TEXTCOLOR', (0, 0), (-1, 0), primary_color),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(ct)
        story.append(Spacer(1, 10))

    # 5. SWOT & Risk Summary
    swot = dossier_data.get("swot") or {}
    if swot:
        story.append(Paragraph("4. SWOT & Risk Matrix", section_heading))
        # strengths/weaknesses items are {"text", "sourceIds"} objects (see
        # docs/unique-features-plan.md §5.1) - str() covers any
        # older/plain-string shape too.
        def _texts(items):
            return [item.get("text", "") if isinstance(item, dict) else str(item) for item in items]

        strengths = ", ".join(_texts(swot.get("strengths") or []) or ["N/A"])
        weaknesses = ", ".join(_texts(swot.get("weaknesses") or []) or ["N/A"])
        story.append(Paragraph(f"<b>Core Strengths:</b> {strengths}", body_style))
        story.append(Paragraph(f"<b>Identified Weaknesses:</b> {weaknesses}", body_style))

    _append_five_pillar_sections(story, dossier_data, section_heading, body_style, primary_color)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _table(rows, col_widths, header_color):
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), header_color),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    return table


def _append_five_pillar_sections(story, dossier_data, section_heading, body_style, header_color) -> None:
    """Five-pillar sections (docs/23): Voice-of-Market quotes, the Market
    Viability & Dynamics breakdown, strategic wedges, the delivery roadmap
    and commercial economics - so a shared PDF carries the same decision
    material as the on-screen report. Every block is skipped when its field
    is missing (older sessions), and every value is escaped since all of it
    is model- or source-derived text.
    """
    market_opp = dossier_data.get("marketOpportunity") or {}
    white_space = dossier_data.get("whiteSpace") or {}
    mvp = dossier_data.get("mvp") or {}
    gtm = dossier_data.get("gtm") or {}
    section = 5

    def e(value) -> str:
        return escape(str(value or ""))

    quotes = [q for q in market_opp.get("voiceOfMarket") or [] if isinstance(q, dict) and q.get("quote")]
    if quotes:
        story.append(Paragraph(f"{section}. Voice of the Market", section_heading))
        section += 1
        for quote in quotes[:3]:
            source = quote.get("speakerOrSource") or quote.get("url") or "source"
            story.append(Paragraph(
                f"<i>&ldquo;{e(quote['quote'])}&rdquo;</i> &mdash; {e(source)} ({e(quote.get('taggedDimension'))})",
                body_style,
            ))

    dimensions = [d for d in (market_opp.get("viabilityIndex") or {}).get("dimensions") or [] if isinstance(d, dict)]
    if dimensions:
        story.append(Paragraph(f"{section}. Market Viability & Dynamics", section_heading))
        section += 1
        rows = [["Axis", "Score", "Evidence", "Why"]]
        for d in dimensions:
            status = (d.get("provenance") or {}).get("status") or ("grounded" if d.get("sourceIds") else "inferred")
            rows.append([
                Paragraph(f"<b>{e(d.get('name'))}</b>", body_style),
                Paragraph(f"{e(d.get('score'))} / 5 ({e(d.get('rating'))})", body_style),
                Paragraph(e(status.capitalize()), body_style),
                Paragraph(e(d.get("rationale")), body_style),
            ])
        story.append(_table(rows, [120, 70, 60, 270], header_color))
        story.append(Spacer(1, 10))

    blueprints = [b for b in white_space.get("blueprints") or [] if isinstance(b, dict)]
    if blueprints:
        story.append(Paragraph(f"{section}. Strategic Wedges", section_heading))
        section += 1
        for blueprint in blueprints:
            vectors = blueprint.get("vectors") or {}
            title = blueprint.get("segment") or blueprint.get("opportunityTitle")
            story.append(Paragraph(
                f"<b>{e(title)}</b> ({e(blueprint.get('convictionPercent'))}% conviction): {e(vectors.get('asymmetricWedge'))}",
                body_style,
            ))
            if blueprint.get("keyRisk"):
                story.append(Paragraph(f"Key risk: {e(blueprint['keyRisk'])}", body_style))

    roadmap = mvp.get("deliveryRoadmap") or {}
    phases = [p for p in roadmap.get("phases") or [] if isinstance(p, dict)]
    if phases:
        story.append(Paragraph(f"{section}. Delivery Roadmap (estimate)", section_heading))
        section += 1
        rows = [["Weeks", "Phase", "Deliverables", "Exit gate"]]
        start = 1
        for phase in phases:
            weeks = max(1, int(phase.get("durationWeeks") or 1))
            end = start + weeks - 1
            rows.append([
                Paragraph(f"{start}&ndash;{end}" if end > start else str(start), body_style),
                Paragraph(f"<b>{e(phase.get('phaseName'))}</b>", body_style),
                Paragraph("; ".join(e(x) for x in phase.get("coreDeliverables") or []), body_style),
                Paragraph("; ".join(e(x) for x in phase.get("exitGateMilestones") or []), body_style),
            ])
            start = end + 1
        story.append(_table(rows, [45, 125, 190, 160], header_color))
        story.append(Spacer(1, 10))

    commercial = gtm.get("commercialModel") or {}
    economics = commercial.get("unitEconomics") or {}
    tiers = [t for t in commercial.get("pricingTiers") or [] if isinstance(t, dict)]
    if economics or tiers:
        story.append(Paragraph(f"{section}. Commercial Economics (estimate)", section_heading))
        if economics:
            story.append(Paragraph(
                f"<b>CAC:</b> {e(economics.get('estimatedCac'))} &nbsp; <b>ARPU:</b> {e(economics.get('targetArpu'))} &nbsp; "
                f"<b>Payback:</b> {e(economics.get('paybackHorizonMonths'))} &nbsp; <b>LTV:CAC:</b> {e(economics.get('ltvToCacRatio'))}",
                body_style,
            ))
            if economics.get("economicRationale"):
                story.append(Paragraph(e(economics["economicRationale"]), body_style))
        if tiers:
            story.append(Paragraph(
                "<b>Pricing tiers:</b> " + "; ".join(
                    f"{e(t.get('tierName'))} {e(t.get('price'))} {e(t.get('billingCycle'))}" for t in tiers
                ),
                body_style,
            ))
