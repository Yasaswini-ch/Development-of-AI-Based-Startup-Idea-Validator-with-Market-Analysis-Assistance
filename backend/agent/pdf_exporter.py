"""
Automated PDF Report Exporter for Milestone 3.

Compiles a validation dossier into a branded, multi-page PDF using ReportLab.
The layout mirrors the on-screen report (frontend ValidationResults.jsx):
idea context, then the verdict with its one headline score, the executive
summary and KPI strip, then the numbered analysis sections. Colours and
type come from the web app's theme (frontend/src/index.css): warm cream
surfaces, terracotta accent, teal info, Fraunces serif headings, Inter body
and JetBrains Mono labels. The fonts are bundled under agent/fonts (SIL OFL)
so the PDF looks the same on every host; if they can't be loaded the
exporter falls back to ReportLab's built-in Helvetica/Times/Courier.
"""

import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .structured_output import extract_inline_citations

logger = logging.getLogger(__name__)

# ── Theme (frontend/src/index.css @theme) ──────────────────────────────────
SURFACE = colors.HexColor("#f6f2ec")
PANEL = colors.HexColor("#fffdfa")
BORDER = colors.HexColor("#e6dfd3")
BORDER_STRONG = colors.HexColor("#c9baa0")
TEXT = colors.HexColor("#262220")
MUTED = colors.HexColor("#8a8178")
MUTED_STRONG = colors.HexColor("#6b6259")
ACCENT = colors.HexColor("#e0654b")
INFO = colors.HexColor("#2f7a6b")
SUCCESS = colors.HexColor("#5c8a6b")
DANGER = colors.HexColor("#8c3a2e")
WARNING = colors.HexColor("#94600f")
WARNING_BRIGHT = colors.HexColor("#d49a32")

PAGE_W, PAGE_H = letter
MARGIN_X = 48
MARGIN_TOP = 56
MARGIN_BOTTOM = 54
# SimpleDocTemplate's frame pads 6pt on each side; full-width tables are
# sized to the padded width so they line up with paragraph text.
FRAME_PAD = 6
CONTENT_W = PAGE_W - 2 * MARGIN_X - 2 * FRAME_PAD
EDGE = MARGIN_X + FRAME_PAD

# Same decision → colour mapping as VerdictCard.jsx.
_DECISION_COLORS = {"pursue": SUCCESS, "validate_first": ACCENT, "rethink": DANGER}

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONTS = {"serif": "Times-Roman", "serif_bold": "Times-Bold", "serif_italic": "Times-Italic",
          "sans": "Helvetica", "sans_bold": "Helvetica-Bold",
          "mono": "Courier", "mono_bold": "Courier-Bold"}
_fonts_ready = False


def _register_fonts() -> None:
    """Register the bundled brand fonts once per process. Any failure (a
    missing or unreadable file) leaves the built-in fallbacks in place."""
    global _fonts_ready
    if _fonts_ready:
        return
    _fonts_ready = True
    wanted = {
        "serif": ("Affinity-Fraunces", "Fraunces-Regular.ttf"),
        "serif_bold": ("Affinity-Fraunces-SemiBold", "Fraunces-SemiBold.ttf"),
        "serif_italic": ("Affinity-Fraunces-Italic", "Fraunces-MediumItalic.ttf"),
        "sans": ("Affinity-Inter", "Inter-Regular.ttf"),
        "sans_bold": ("Affinity-Inter-SemiBold", "Inter-SemiBold.ttf"),
        "mono": ("Affinity-Mono", "JetBrainsMono-Medium.ttf"),
        "mono_bold": ("Affinity-Mono-Bold", "JetBrainsMono-Bold.ttf"),
    }
    try:
        for name, filename in wanted.values():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, os.path.join(_FONT_DIR, filename)))
    except Exception:
        logger.warning("Brand fonts unavailable, PDF falls back to built-in fonts", exc_info=True)
        return
    for key, (name, _) in wanted.items():
        _FONTS[key] = name
    # So <b>/<i> inside body and heading paragraphs pick the right faces.
    pdfmetrics.registerFontFamily(
        _FONTS["sans"], normal=_FONTS["sans"], bold=_FONTS["sans_bold"],
        italic=_FONTS["serif_italic"], boldItalic=_FONTS["serif_italic"],
    )
    pdfmetrics.registerFontFamily(
        _FONTS["serif"], normal=_FONTS["serif"], bold=_FONTS["serif_bold"],
        italic=_FONTS["serif_italic"], boldItalic=_FONTS["serif_italic"],
    )


def _hex(color) -> str:
    return "#" + color.hexval()[2:]


def _e(value) -> str:
    return escape(str(value if value is not None else ""))


def _styles() -> Dict[str, ParagraphStyle]:
    f = _FONTS

    def style(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "brand": style("Brand", fontName=f["mono_bold"], fontSize=9, leading=12, textColor=TEXT),
        "eyebrow": style("Eyebrow", fontName=f["mono_bold"], fontSize=7.5, leading=10, textColor=ACCENT),
        "label": style("Label", fontName=f["mono"], fontSize=7, leading=9.5, textColor=MUTED),
        "label_right": style("LabelRight", fontName=f["mono"], fontSize=7, leading=9.5, textColor=MUTED, alignment=TA_RIGHT),
        "title": style("Title", fontName=f["serif_bold"], fontSize=26, leading=31, textColor=TEXT),
        "meta": style("Meta", fontName=f["mono"], fontSize=7.5, leading=11, textColor=MUTED),
        "section": style("Section", fontName=f["mono_bold"], fontSize=8.5, leading=11, textColor=TEXT),
        "h3": style("H3", fontName=f["serif_bold"], fontSize=12, leading=15, textColor=TEXT),
        "headline": style("Headline", fontName=f["serif"], fontSize=15, leading=20, textColor=TEXT),
        "score": style("Score", fontName=f["serif"], fontSize=38, leading=40, textColor=TEXT, alignment=TA_RIGHT),
        "stat": style("Stat", fontName=f["serif"], fontSize=24, leading=27, alignment=TA_CENTER),
        "stat_label": style("StatLabel", fontName=f["mono_bold"], fontSize=7, leading=9, textColor=TEXT, alignment=TA_CENTER),
        "stat_sub": style("StatSub", fontName=f["sans"], fontSize=7, leading=9, textColor=MUTED, alignment=TA_CENTER),
        "fact": style("Fact", fontName=f["serif"], fontSize=13, leading=16, textColor=TEXT),
        "body": style("Body", fontName=f["sans"], fontSize=9, leading=13.5, textColor=TEXT),
        "body_muted": style("BodyMuted", fontName=f["sans"], fontSize=8.5, leading=12.5, textColor=MUTED_STRONG),
        "cell": style("Cell", fontName=f["sans"], fontSize=8.3, leading=11.5, textColor=TEXT),
        "cell_bold": style("CellBold", fontName=f["sans_bold"], fontSize=8.3, leading=11.5, textColor=TEXT),
        "th": style("TH", fontName=f["mono_bold"], fontSize=6.8, leading=9, textColor=MUTED_STRONG),
        "quote": style("Quote", fontName=f["serif_italic"], fontSize=11, leading=15.5, textColor=TEXT),
        "bullet": style("Bullet", fontName=f["sans"], fontSize=8.5, leading=12.5, textColor=TEXT),
    }


# ── Building blocks ────────────────────────────────────────────────────────

def _card(content, width=CONTENT_W, border=BORDER, border_width=0.75, background=PANEL, padding=14):
    """A rounded panel, like the web report's `rounded-2xl border bg-panel` cards."""
    rows = [[c] for c in content] if isinstance(content, list) else [[content]]
    table = Table(rows, colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), border_width, border),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 0), padding),
        ("BOTTOMPADDING", (0, -1), (-1, -1), padding),
    ]))
    return table


def _pill(text, color, s, filled=False):
    """A small uppercase mono badge (verdict label, 'Estimate', provenance)."""
    style = ParagraphStyle("Pill", parent=s["label"], fontName=_FONTS["mono_bold"], fontSize=6.8,
                           textColor=PANEL if filled else color, alignment=TA_CENTER)
    label = Paragraph(_e(text).upper(), style)
    width = pdfmetrics.stringWidth(str(text).upper(), style.fontName, style.fontSize) + 14
    table = Table([[label]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color if filled else colors.Color(color.red, color.green, color.blue, alpha=0.1)),
        ("BOX", (0, 0), (-1, -1), 0.6, color),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    table.hAlign = "LEFT"
    return table


class _Dot(Flowable):
    """The accent dot that leads every mono section label on the web."""

    def __init__(self, color=ACCENT, size=4.5):
        super().__init__()
        self.color, self.size = color, size
        self.width = self.height = size

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.circle(self.size / 2, self.size / 2, self.size / 2, stroke=0, fill=1)


class _Meter(Flowable):
    """A 0–max bar for the viability dimension scores."""

    def __init__(self, value, maximum=5, width=46, height=4.5, color=INFO):
        super().__init__()
        self.value, self.maximum, self.color = value, maximum, color
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        c.setFillColor(BORDER)
        c.roundRect(0, 0, self.width, self.height, self.height / 2, stroke=0, fill=1)
        try:
            ratio = max(0.0, min(1.0, float(self.value) / self.maximum))
        except (TypeError, ValueError):
            return
        if ratio:
            c.setFillColor(self.color)
            c.roundRect(0, 0, max(self.height, self.width * ratio), self.height, self.height / 2, stroke=0, fill=1)


def _label_row(text, s, dot_color=ACCENT, right=None):
    """`● LABEL` in mono, optionally with a badge flowable on the right."""
    cells = [_Dot(dot_color), Paragraph(_e(text).upper(), s["section"])]
    widths = [10, None]
    if right is not None:
        cells.append(right)
        widths = [10, CONTENT_W - 10 - right.wrap(CONTENT_W, 20)[0], right.wrap(CONTENT_W, 20)[0]]
    table = Table([cells], colWidths=widths)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("ALIGN", (-1, 0), (-1, 0), "RIGHT"),
    ]))
    table.hAlign = "LEFT"
    return table


class _Sections:
    """Numbers the report sections (§01, §02, ...) as they're added, so a
    section skipped for missing data doesn't leave a gap in the numbering."""

    def __init__(self, story, s):
        self.story, self.s, self.n = story, s, 0

    def add(self, title, estimate=False):
        self.n += 1
        badge = _pill("Estimate", WARNING, self.s) if estimate else None
        heading = Table(
            [[Paragraph(f"§{self.n:02d}", ParagraphStyle("Num", parent=self.s["section"], textColor=ACCENT)),
              _label_row(title, self.s, right=badge)]],
            colWidths=[30, CONTENT_W - 30],
        )
        heading.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.9, BORDER_STRONG),
        ]))
        # Never strand a heading at the foot of a page.
        self.story.append(CondPageBreak(120))
        self.story.append(Spacer(1, 16))
        self.story.append(heading)
        self.story.append(Spacer(1, 10))


def _data_table(rows, col_widths, s, zebra=True):
    """A web-style data table: mono uppercase header on the cream surface,
    hairline row rules instead of a full grid."""
    header = [Paragraph(_e(h).upper(), s["th"]) for h in rows[0]]
    table = Table([header] + rows[1:], colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, BORDER_STRONG),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 1), (-1, -1), PANEL),
    ]
    if zebra:
        for i in range(2, len(rows), 2):
            cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fbf8f3")))
    table.setStyle(TableStyle(cmds))
    return table


def _fact_grid(facts, s):
    """Label-over-value facts in one panel split by hairlines (market size,
    CAGR, unit economics) - one card keeps the columns the same height."""
    facts = [(label, value) for label, value in facts if value not in (None, "")]
    if not facts:
        return None
    inner = CONTENT_W - 28
    cells = [[Paragraph(_e(label).upper(), s["label"]), Spacer(1, 4), Paragraph(_e(value), s["fact"])]
             for label, value in facts]
    row = Table([cells], colWidths=[inner / len(cells)] * len(cells))
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([_card(row, padding=14), Spacer(1, 10)])


def _bullets(items, s, color=BORDER_STRONG, style="bullet"):
    base = s[style]
    indented = ParagraphStyle(f"{base.name}Bullet", parent=base, leftIndent=10, bulletIndent=0, spaceAfter=2)
    dot = f'<bullet><font color="{_hex(color)}" size="6">\u25cf</font></bullet>'
    return [Paragraph(dot + _e(item), indented) for item in items if str(item or "").strip()]


def _texts(items) -> List[str]:
    """SWOT items are {"text", "sourceIds"} objects (docs/unique-features-plan.md
    §5.1); str() covers any older plain-string shape too."""
    return [item.get("text", "") if isinstance(item, dict) else str(item) for item in items or []]


def _concept_title(idea: str) -> str:
    """Short title for the cover and running header - first sentence,
    capped, same rule as IdeaDossier.jsx. The full idea is printed in the
    idea context panel."""
    first = (idea or "").strip().split(".")[0].strip() or "Startup concept"
    return first if len(first) <= 90 else first[:87].rstrip() + "…"


# ── Page chrome ────────────────────────────────────────────────────────────

def _page_decorator(concept: str, generated: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(SURFACE)
        canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        # Accent rule across the top of every page.
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 4, PAGE_W, 4, stroke=0, fill=1)
        if doc.page > 1:
            canvas.setFont(_FONTS["mono_bold"], 7)
            canvas.setFillColor(TEXT)
            canvas.drawString(EDGE, PAGE_H - 30, "AFFINITY")
            canvas.setFont(_FONTS["mono"], 7)
            canvas.setFillColor(MUTED)
            short = concept if len(concept) <= 70 else concept[:67] + "…"
            canvas.drawRightString(PAGE_W - EDGE, PAGE_H - 30, short)
            canvas.setStrokeColor(BORDER)
            canvas.setLineWidth(0.6)
            canvas.line(EDGE, PAGE_H - 38, PAGE_W - EDGE, PAGE_H - 38)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(EDGE, 36, PAGE_W - EDGE, 36)
        canvas.setFont(_FONTS["mono"], 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(EDGE, 24, f"Affinity market validation report  ·  {generated}")
        canvas.drawRightString(PAGE_W - EDGE, 24, f"Page {doc.page}")
        canvas.restoreState()

    return draw


# ── Report sections ────────────────────────────────────────────────────────

def _cover(story, d, s, concept, generated):
    story.append(Table(
        [[_Dot(ACCENT, 6), Paragraph("AFFINITY", s["brand"]),
          Paragraph(f"MARKET VALIDATION REPORT  ·  {_e(generated).upper()}", s["label_right"])]],
        colWidths=[12, 120, CONTENT_W - 132],
        style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)],
    ))
    story.append(Spacer(1, 26))
    story.append(Paragraph("§ IDEA CONTEXT", s["eyebrow"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(_e(concept), s["title"]))
    story.append(Spacer(1, 14))

    idea = d.get("idea") or d.get("ideaTitle") or "Startup concept"
    target = d.get("targetCustomer")
    problem = d.get("problem")
    not_given = f'<font color="{_hex(MUTED)}"><i>Not specified</i></font>'

    def block(label, value):
        return [Paragraph(label, s["label"]), Spacer(1, 3),
                Paragraph(_e(value) if value else not_given, s["body"])]

    half = (CONTENT_W - 28 - 16) / 2
    context = Table(
        [[block("IDEA", idea), ""],
         [block("TARGET CUSTOMER", target), block("PROBLEM", problem)]],
        colWidths=[half + 16, half],
    )
    context.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 16),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BORDER),
        ("TOPPADDING", (0, 1), (-1, 1), 10),
    ]))
    story.append(_card(context))


def _verdict(story, d, s):
    verdict = d.get("verdict") or {}
    market_opp = d.get("marketOpportunity") or {}
    opp_score = market_opp.get("opportunityScore", (d.get("opportunityScore") or {}).get("score"))
    has_score = isinstance(verdict.get("score"), (int, float))
    color = _DECISION_COLORS.get(verdict.get("decision"), ACCENT)
    inner_w = CONTENT_W - 28

    if verdict.get("label") or has_score:
        head = [_label_row("Verdict", s, dot_color=color)]
        if verdict.get("label"):
            head += [Spacer(1, 8), _pill(verdict["label"], color, s, filled=True)]
        if verdict.get("headline"):
            head += [Spacer(1, 8), Paragraph(_e(verdict["headline"]), s["headline"])]
        score_cell = ""
        if has_score:
            score_cell = [
                Paragraph(f'{_e(verdict["score"])}<font name="{_FONTS["mono"]}" size="9" color="{_hex(MUTED)}">/100</font>', s["score"]),
                Spacer(1, 4),
                Paragraph(_e(verdict.get("scoreName") or "Score").upper(), s["label_right"]),
            ]
        top = Table([[head, score_cell]], colWidths=[inner_w - 130, 130])
        top.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        content = [top]
        # The first reason restates the score ("Market viability is 58/100.")
        # - redundant next to the big number, same filter as VerdictCard.jsx.
        prefix = f"{verdict.get('scoreName')} is {verdict.get('score')}/100"
        reasons = [r for r in verdict.get("reasons") or []
                   if not (has_score and verdict.get("scoreName") and str(r).startswith(prefix))]
        if reasons:
            content.append(Spacer(1, 8))
            content += _bullets(reasons, s, style="body_muted")
        if verdict.get("nextStep"):
            step = Table([[Paragraph(
                f'<font name="{_FONTS["mono_bold"]}" size="7.5" color="{_hex(ACCENT)}">NEXT STEP&nbsp;&nbsp;</font>{_e(verdict["nextStep"])}',
                s["body"])]], colWidths=[inner_w])
            step.setStyle(TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            content += [Spacer(1, 8), step]
        story.append(Spacer(1, 12))
        story.append(KeepTogether(_card(content, border=color, border_width=1.4, padding=18)))
    elif opp_score not in (None, "N/A"):
        # Older sessions carry no verdict - the opportunity score is the headline.
        story.append(Spacer(1, 12))
        story.append(_card([
            _label_row("Feasibility opportunity score", s),
            Spacer(1, 6),
            Paragraph(f'{_e(opp_score)}<font name="{_FONTS["mono"]}" size="9" color="{_hex(MUTED)}">/100</font>',
                      ParagraphStyle("OppScore", parent=s["score"], alignment=0)),
        ], padding=18))


def _summary_and_stats(story, d, s):
    summary = d.get("summary") or "Automated feasibility evaluation compiled from live web search retrieval."
    story.append(Spacer(1, 12))
    story.append(KeepTogether(_card([_label_row("Executive summary", s), Spacer(1, 7),
                                     Paragraph(_e(extract_inline_citations(summary)[0]), s["body"])])))

    # KPI strip - same four counts as StatsStrip.jsx, hidden with no sources.
    results = d.get("results") or []
    if not results:
        return
    stats = [
        (len(results), "Sources", "Live web search", ACCENT),
        (len((d.get("competitors") or {}).get("competitors") or []), "Competitors", "Direct & indirect", INFO),
        (len((d.get("whiteSpace") or {}).get("opportunities") or []), "Market gaps", "Whitespace found", SUCCESS),
        (len((d.get("marketOpportunity") or {}).get("segments") or []), "Personas", "Customer segments", ACCENT),
    ]
    cells = [[Paragraph(str(v), ParagraphStyle(f"Stat{i}", parent=s["stat"], textColor=c)),
              Spacer(1, 3), Paragraph(label.upper(), s["stat_label"]), Paragraph(sub, s["stat_sub"])]
             for i, (v, label, sub, c) in enumerate(stats)]
    strip = Table([cells], colWidths=[(CONTENT_W - 28) / 4] * 4)
    strip.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 12))
    story.append(_card(strip, padding=14))


def _market(story, d, s, sections):
    market_opp = d.get("marketOpportunity") or {}
    if not market_opp:
        return
    sections.add("Market size & growth")
    verdict = d.get("verdict") or {}
    opp_score = market_opp.get("opportunityScore", (d.get("opportunityScore") or {}).get("score"))
    # Older reports can still carry raw "[src-N]" markers in marketSize.
    size = extract_inline_citations(market_opp.get("marketSize") or "Emerging sector")[0]
    facts = [("Estimated TAM / SAM", size), ("CAGR", market_opp.get("cagr") or "N/A")]
    # Without a verdict score the opportunity score is already the headline
    # number above; with one, it's a labelled secondary metric here.
    if isinstance(verdict.get("score"), (int, float)) and opp_score not in (None, "N/A", 0):
        facts.append(("Opportunity score (secondary)", f"{opp_score} / 100"))
    story.append(_fact_grid(facts, s))

    segments = [seg for seg in market_opp.get("segments") or [] if isinstance(seg, dict)]
    if segments:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Customer segments", s["h3"]))
        story.append(Spacer(1, 6))
        rows = [["Segment", "Pain points / needs"]]
        for seg in segments[:3]:
            rows.append([Paragraph(_e(seg.get("segment")), s["cell_bold"]), Paragraph(_e(seg.get("painPoints")), s["cell"])])
        story.append(_data_table(rows, [160, CONTENT_W - 160], s))


def _competitors(story, d, s, sections):
    data = d.get("competitors") or {}
    comp_list = [c for c in data.get("competitors") or [] if isinstance(c, dict)]
    if not comp_list:
        return
    sections.add("Competitor landscape & positioning")
    # Profiled competitors (competitor_agent._profile_with_llm) carry a
    # stated pricing note and weaknesses; NER-only ones fall back to the
    # rough price bucket and feature breadth.
    if data.get("profiled"):
        rows = [["Competitor", "Type", "Pricing", "Key weakness"]]
        for c in comp_list[:5]:
            weaknesses = c.get("weaknesses") or []
            rows.append([
                Paragraph(_e(c.get("name")), s["cell_bold"]),
                Paragraph(_e(c.get("classification") or "unknown"), s["cell"]),
                Paragraph(_e(c.get("pricing") or c.get("estimatedPrice") or "unknown"), s["cell"]),
                Paragraph(_e(weaknesses[0] if weaknesses else "unknown"), s["cell"]),
            ])
        widths = [120, 70, 130, CONTENT_W - 320]
    else:
        rows = [["Competitor", "Pricing tier", "Feature breadth"]]
        for c in comp_list[:5]:
            rows.append([
                Paragraph(_e(c.get("name")), s["cell_bold"]),
                Paragraph(_e(c.get("priceBucket") or c.get("estimatedPrice") or "unknown"), s["cell"]),
                Paragraph(_e(c.get("featureBreadth") or "unknown"), s["cell"]),
            ])
        widths = [CONTENT_W - 300, 150, 150]
    story.append(_data_table(rows, widths, s))


def _swot(story, d, s, sections):
    swot = d.get("swot") or {}
    if not swot:
        return
    quads = [
        ("Strengths", _texts(swot.get("strengths")), SUCCESS),
        ("Weaknesses", _texts(swot.get("weaknesses")), DANGER),
        ("Opportunities", _texts(swot.get("opportunities")), INFO),
        ("Threats", _texts(swot.get("threats")), WARNING_BRIGHT),
    ]
    risks = [r for r in swot.get("risks") or [] if isinstance(r, dict) and r.get("risk")]
    if not any(items for _, items, _ in quads) and not risks:
        return
    sections.add("SWOT & risk matrix")
    gap = 8
    width = (CONTENT_W - gap) / 2

    def quad(title, items, color):
        body = _bullets(items, s, color=color) or [Paragraph("None identified.", s["body_muted"])]
        return _card([_label_row(title, s, dot_color=color), Spacer(1, 6)] + body, width=width, padding=12)

    grid = Table([[quad(*quads[0]), quad(*quads[1])], [quad(*quads[2]), quad(*quads[3])]],
                 colWidths=[width + gap, width])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), gap), ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), gap),
    ]))
    story.append(grid)

    if risks:
        level_color = {"high": DANGER, "medium": WARNING, "low": SUCCESS}

        def level(value):
            value = str(value or "").lower()
            return Paragraph(f'<font color="{_hex(level_color.get(value, MUTED_STRONG))}">{_e(value.capitalize() or "—")}</font>',
                             s["cell_bold"])

        story.append(Spacer(1, 4))
        story.append(Paragraph("Key risks", s["h3"]))
        story.append(Spacer(1, 6))
        rows = [["Risk", "Severity", "Likelihood", "Mitigation"]]
        for r in risks:
            rows.append([Paragraph(_e(r.get("risk")), s["cell"]), level(r.get("severity")), level(r.get("likelihood")),
                         Paragraph(_e(r.get("mitigation") or "—"), s["cell"])])
        story.append(_data_table(rows, [180, 58, 62, CONTENT_W - 300], s))


def _voice_of_market(story, d, s, sections):
    quotes = [q for q in (d.get("marketOpportunity") or {}).get("voiceOfMarket") or []
              if isinstance(q, dict) and q.get("quote")]
    if not quotes:
        return
    sections.add("Voice of the market")
    for quote in quotes[:3]:
        source = quote.get("speakerOrSource") or quote.get("url") or "source"
        meta = f"— {_e(source)}"
        if quote.get("taggedDimension"):
            meta += f'&nbsp;&nbsp;<font color="{_hex(ACCENT)}">{_e(quote["taggedDimension"]).upper()}</font>'
        block = Table([[[Paragraph(f"&ldquo;{_e(quote['quote'])}&rdquo;", s["quote"]), Spacer(1, 5),
                         Paragraph(meta, s["label"])]]], colWidths=[CONTENT_W])
        block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PANEL),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 8))


def _viability(story, d, s, sections):
    dims = [x for x in ((d.get("marketOpportunity") or {}).get("viabilityIndex") or {}).get("dimensions") or []
            if isinstance(x, dict)]
    if not dims:
        return
    sections.add("Market viability & dynamics")
    rows = [["Axis", "Score", "Evidence", "Why"]]
    for x in dims:
        status = (x.get("provenance") or {}).get("status") or ("grounded" if x.get("sourceIds") else "inferred")
        color = INFO if status == "grounded" else WARNING
        score = [Paragraph(f'{_e(x.get("score"))}<font color="{_hex(MUTED)}"> / 5</font>'
                           + (f'&nbsp;&nbsp;<font size="7" color="{_hex(MUTED)}">{_e(x.get("rating"))}</font>' if x.get("rating") else ""),
                           s["cell_bold"]),
                 Spacer(1, 4), _Meter(x.get("score"))]
        rows.append([
            Paragraph(_e(x.get("name")), s["cell_bold"]),
            score,
            _pill(str(status).capitalize(), color, s),
            Paragraph(_e(x.get("rationale")), s["cell"]),
        ])
    story.append(_data_table(rows, [112, 82, 70, CONTENT_W - 264], s))


def _wedges(story, d, s, sections):
    blueprints = [b for b in (d.get("whiteSpace") or {}).get("blueprints") or [] if isinstance(b, dict)]
    if not blueprints:
        return
    sections.add("Strategic wedges")
    for blueprint in blueprints:
        vectors = blueprint.get("vectors") or {}
        title = blueprint.get("segment") or blueprint.get("opportunityTitle")
        head = [Paragraph(_e(title), s["h3"])]
        conviction = blueprint.get("convictionPercent")
        badge = _pill(f"{conviction}% conviction", INFO, s) if conviction not in (None, "") else ""
        bw = badge.wrap(CONTENT_W, 20)[0] if badge else 0
        top = Table([[head, badge]], colWidths=[CONTENT_W - 28 - bw, bw])
        top.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        content = [top]
        if vectors.get("asymmetricWedge"):
            content += [Spacer(1, 6), Paragraph("WEDGE", s["label"]), Spacer(1, 2),
                        Paragraph(_e(vectors["asymmetricWedge"]), s["body"])]
        if blueprint.get("keyRisk"):
            content += [Spacer(1, 6), Paragraph(
                f'<font name="{_FONTS["mono_bold"]}" size="7" color="{_hex(WARNING)}">KEY RISK&nbsp;&nbsp;</font>{_e(blueprint["keyRisk"])}',
                s["body_muted"])]
        story.append(KeepTogether(_card(content, padding=14)))
        story.append(Spacer(1, 8))


def _roadmap(story, d, s, sections):
    phases = [p for p in ((d.get("mvp") or {}).get("deliveryRoadmap") or {}).get("phases") or [] if isinstance(p, dict)]
    if not phases:
        return
    sections.add("Delivery roadmap", estimate=True)
    rows = [["Weeks", "Phase", "Deliverables", "Exit gate"]]
    start = 1
    for phase in phases:
        try:
            weeks = max(1, int(phase.get("durationWeeks") or 1))
        except (TypeError, ValueError):
            weeks = 1
        end = start + weeks - 1
        rows.append([
            Paragraph(f"{start}&ndash;{end}" if end > start else str(start),
                      ParagraphStyle("Weeks", parent=s["cell_bold"], fontName=_FONTS["mono_bold"], textColor=ACCENT)),
            Paragraph(_e(phase.get("phaseName")), s["cell_bold"]),
            _bullets(phase.get("coreDeliverables") or [], s, color=INFO) or Paragraph("—", s["cell"]),
            _bullets(phase.get("exitGateMilestones") or [], s, color=SUCCESS) or Paragraph("—", s["cell"]),
        ])
        start = end + 1
    story.append(_data_table(rows, [48, 110, (CONTENT_W - 158) / 2, (CONTENT_W - 158) / 2], s, zebra=False))


def _economics(story, d, s, sections):
    commercial = (d.get("gtm") or {}).get("commercialModel") or {}
    economics = commercial.get("unitEconomics") or {}
    tiers = [t for t in commercial.get("pricingTiers") or [] if isinstance(t, dict)]
    if not economics and not tiers:
        return
    sections.add("Commercial economics", estimate=True)
    if economics:
        grid = _fact_grid([
            ("CAC", economics.get("estimatedCac")),
            ("ARPU", economics.get("targetArpu")),
            ("Payback", economics.get("paybackHorizonMonths")),
            ("LTV : CAC", economics.get("ltvToCacRatio")),
        ], s)
        if grid is not None:
            story.append(grid)
        if economics.get("economicRationale"):
            story.append(Paragraph(_e(economics["economicRationale"]), s["body_muted"]))
            story.append(Spacer(1, 8))
    if tiers:
        story.append(Paragraph("Pricing tiers", s["h3"]))
        story.append(Spacer(1, 6))
        rows = [["Tier", "Price", "Billing"]]
        for t in tiers:
            rows.append([Paragraph(_e(t.get("tierName")), s["cell_bold"]),
                         Paragraph(_e(t.get("price")), s["cell"]),
                         Paragraph(_e(t.get("billingCycle") or "—"), s["cell"])])
        story.append(_data_table(rows, [CONTENT_W - 260, 130, 130], s))


def build_story(dossier_data: Dict[str, Any], generated: str) -> list:
    """The report's flowables in reading order: idea context, verdict,
    summary + KPI strip, then the numbered analysis sections (each skipped
    when its data is missing, e.g. older sessions)."""
    _register_fonts()
    d = dossier_data or {}
    s = _styles()
    story: list = []
    _cover(story, d, s, _concept_title(d.get("idea") or d.get("ideaTitle") or ""), generated)
    _verdict(story, d, s)
    _summary_and_stats(story, d, s)

    sections = _Sections(story, s)
    _market(story, d, s, sections)
    _competitors(story, d, s, sections)
    _swot(story, d, s, sections)
    _voice_of_market(story, d, s, sections)
    _viability(story, d, s, sections)
    _wedges(story, d, s, sections)
    _roadmap(story, d, s, sections)
    _economics(story, d, s, sections)
    return story


def generate_dossier_pdf(dossier_data: Dict[str, Any]) -> bytes:
    """Generate the branded PDF report for a validation dossier. Every field
    is read defensively (older sessions miss the newer ones) and every value
    is escaped, since all of it is model- or source-derived text."""
    d = dossier_data or {}
    concept = _concept_title(d.get("idea") or d.get("ideaTitle") or "")
    generated = datetime.now(timezone.utc).strftime("%d %b %Y")
    story = build_story(d, generated)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=f"Affinity report: {concept}", author="Affinity", subject="Market validation report",
    )
    decorate = _page_decorator(concept, generated)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    buffer.seek(0)
    return buffer.getvalue()
