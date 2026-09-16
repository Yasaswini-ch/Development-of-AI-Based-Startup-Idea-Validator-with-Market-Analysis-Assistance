"""
Automated PDF Report Exporter for Milestone 3.

Compiles validation dossiers into multi-page, executive publication-ready PDF documents
using ReportLab.
"""

import io
import logging
from typing import Any, Dict

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
    story.append(Paragraph("1. Executive Summary & Opportunity Score", section_heading))
    story.append(Paragraph(f"<b>Feasibility Opportunity Score:</b> {opp_score} / 100", body_style))
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
        c_table_data = [["Competitor Name", "Pricing Tier", "Feature Breadth"]]
        for c in comp_list[:5]:
            c_table_data.append([
                Paragraph(f"<b>{c.get('name', '')}</b>", body_style),
                Paragraph(c.get('priceBucket', c.get('estimatedPrice', 'unknown')), body_style),
                Paragraph(c.get('featureBreadth', 'unknown'), body_style),
            ])
        ct = Table(c_table_data, colWidths=[200, 160, 160])
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
        strengths = ", ".join(swot.get("strengths") or ["N/A"])
        weaknesses = ", ".join(swot.get("weaknesses") or ["N/A"])
        story.append(Paragraph(f"<b>Core Strengths:</b> {strengths}", body_style))
        story.append(Paragraph(f"<b>Identified Weaknesses:</b> {weaknesses}", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
