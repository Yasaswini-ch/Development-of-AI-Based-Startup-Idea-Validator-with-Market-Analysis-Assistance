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
import re
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


# market_agent.py has no structured "cagr" field - the model is instructed
# (market_analysis_task.md) to fold a CAGR into the free-prose marketSize
# sentence when a source states one, rather than invent a separate figure.
# marketOpportunity.get("cagr") is therefore always absent today; pull the
# percentage back out of that prose instead of printing a permanent N/A. A
# forward-looking "cagr" key (if a future pass ever adds one) still wins.
_CAGR_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?%)\s*(?:CAGR|compound annual growth rate)"
    r"|(?:CAGR|compound annual growth rate)\s*(?:of|:)?\s*(\d{1,3}(?:\.\d+)?%)",
    re.IGNORECASE,
)


def _extract_cagr(market_opp: dict, market_size_text: str) -> str:
    structured = market_opp.get("cagr")
    if structured:
        return str(structured)
    match = _CAGR_RE.search(market_size_text or "")
    if not match:
        return "N/A"
    return f"{match.group(1) or match.group(2)} CAGR"


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


# ── Charts ─────────────────────────────────────────────────────────────────
# Vector charts drawn straight onto the canvas, in the web app's palette.
# Labels and values use text colours; the series colour only fills marks.

def _fit(text, font, size, max_width) -> str:
    """Truncate text with an ellipsis so it fits max_width points."""
    text = str(text or "")
    if pdfmetrics.stringWidth(text, font, size) <= max_width:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _tint(color, alpha):
    return colors.Color(color.red, color.green, color.blue, alpha=alpha)


def _tier_color(percent) -> colors.Color:
    """Same three tiers as ConfidenceDashboard.jsx's tierFor()."""
    if percent >= 67:
        return SUCCESS
    if percent >= 34:
        return ACCENT
    return DANGER


class _HBarChart(Flowable):
    """Labelled horizontal bars on a shared scale: [(label, value, color)]."""

    ROW_H = 17

    def __init__(self, rows, width, maximum=100, fmt=lambda v: f"{v:.0f}%", label_w=118):
        super().__init__()
        self.rows, self.maximum, self.fmt, self.label_w = rows, maximum, fmt, label_w
        self.width, self.height = width, len(rows) * self.ROW_H

    def draw(self):
        c = self.canv
        value_w = 34
        track_x = self.label_w + 6
        track_w = self.width - track_x - value_w
        for i, (label, value, color) in enumerate(self.rows):
            y = self.height - (i + 1) * self.ROW_H + 5
            c.setFont(_FONTS["mono"], 7)
            c.setFillColor(MUTED_STRONG)
            c.drawString(0, y, _fit(str(label).upper(), _FONTS["mono"], 7, self.label_w))
            c.setFillColor(BORDER)
            c.roundRect(track_x, y - 0.5, track_w, 5, 2.5, stroke=0, fill=1)
            ratio = max(0.0, min(1.0, float(value) / self.maximum)) if self.maximum else 0
            if ratio:
                c.setFillColor(color)
                c.roundRect(track_x, y - 0.5, max(5, track_w * ratio), 5, 2.5, stroke=0, fill=1)
            c.setFont(_FONTS["mono_bold"], 7.5)
            c.setFillColor(TEXT)
            c.drawRightString(self.width, y, self.fmt(value))


class _RadarChart(Flowable):
    """Viability profile: one polygon over 0-max rings, like RadarChart in
    frontend/src/components/charts.jsx."""

    def __init__(self, axes, width, size=230, maximum=5, color=ACCENT):
        super().__init__()
        self.axes, self.maximum, self.color = axes, maximum, color
        self.width, self.height = width, size

    def _point(self, value, index, radius):
        import math

        angle = math.pi / 2 - (2 * math.pi / len(self.axes)) * index
        r = max(0.0, min(float(value), self.maximum)) / self.maximum * radius
        return self.width / 2 + r * math.cos(angle), self.height / 2 + r * math.sin(angle)

    def draw(self):
        c = self.canv
        radius = self.height / 2 - 30
        n = len(self.axes)
        c.setLineWidth(0.6)
        c.setStrokeColor(BORDER_STRONG)
        for step in range(1, int(self.maximum) + 1):
            path = c.beginPath()
            for i in range(n):
                x, y = self._point(step, i, radius)
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            path.close()
            c.drawPath(path, stroke=1, fill=0)
        for i in range(n):
            x, y = self._point(self.maximum, i, radius)
            c.line(self.width / 2, self.height / 2, x, y)

        points = [self._point(value, i, radius) for i, (_, value) in enumerate(self.axes)]
        path = c.beginPath()
        for i, (x, y) in enumerate(points):
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.close()
        c.setFillColor(_tint(self.color, 0.18))
        c.setStrokeColor(self.color)
        c.setLineWidth(1.5)
        c.drawPath(path, stroke=1, fill=1)
        c.setFillColor(self.color)
        c.setStrokeColor(PANEL)
        c.setLineWidth(1)
        for x, y in points:
            c.circle(x, y, 2.6, stroke=1, fill=1)

        cx, cy = self.width / 2, self.height / 2
        for i, (label, value) in enumerate(self.axes):
            x, y = self._point(self.maximum, i, radius)
            dx, dy = x - cx, y - cy
            # Push the two-line label outward from the spoke tip, clear of
            # the ring: sideways for side axes, up/down for top/bottom ones.
            x += 8 if dx > 8 else -8 if dx < -8 else 0
            y += 14 if dy > 8 else -12 if dy < -8 else 3
            anchor = c.drawString if dx > 8 else c.drawRightString if dx < -8 else c.drawCentredString
            c.setFont(_FONTS["mono"], 6.5)
            c.setFillColor(MUTED_STRONG)
            anchor(x, y + 1, _fit(str(label).upper(), _FONTS["mono"], 6.5, 120))
            c.setFont(_FONTS["mono_bold"], 7)
            c.setFillColor(TEXT)
            anchor(x, y - 7.5, f"{value:g} / {self.maximum:g}")


class _MatrixChart(Flowable):
    """A 3x3 grid with row/column labels. `cells[(row, col)]` is a list of
    chip labels; `shade(row, col)` returns the cell's fill colour."""

    def __init__(self, width, rows, cols, cells, shade, x_title, y_title, chip_color=ACCENT, cell_h=46):
        super().__init__()
        self.rows, self.cols, self.cells, self.shade = rows, cols, cells, shade
        self.x_title, self.y_title, self.chip_color, self.cell_h = x_title, y_title, chip_color, cell_h
        self.width, self.height = width, cell_h * len(rows) + 28

    def draw(self):
        c = self.canv
        gutter = 58
        gap = 3
        cell_w = (self.width - gutter - gap * (len(self.cols) - 1)) / len(self.cols)
        top = self.height - 14
        c.setFont(_FONTS["mono_bold"], 6.5)
        c.setFillColor(MUTED)
        c.drawString(0, self.height - 7, self.y_title.upper())
        c.drawRightString(self.width, 0, self.x_title.upper() + "  →")
        for ci, (_, col_label) in enumerate(self.cols):
            c.setFont(_FONTS["mono"], 6.5)
            c.setFillColor(MUTED_STRONG)
            c.drawCentredString(gutter + ci * (cell_w + gap) + cell_w / 2, 9, col_label.upper())
        for ri, (row_key, row_label) in enumerate(self.rows):
            y = top - (ri + 1) * self.cell_h + gap / 2
            c.setFont(_FONTS["mono"], 6.5)
            c.setFillColor(MUTED_STRONG)
            c.drawString(0, y + self.cell_h / 2 - 3, row_label.upper())
            for ci, (col_key, _) in enumerate(self.cols):
                x = gutter + ci * (cell_w + gap)
                c.setFillColor(self.shade(row_key, col_key))
                c.setStrokeColor(BORDER)
                c.setLineWidth(0.6)
                c.roundRect(x, y, cell_w, self.cell_h - gap, 4, stroke=1, fill=1)
                self._chips(c, self.cells.get((row_key, col_key)) or [], x + 4, y + self.cell_h - gap - 4, cell_w - 8)

    def _chips(self, c, labels, x, top, max_w):
        font, size, h = _FONTS["sans_bold"], 6.8, 11
        cursor_x, cursor_y, lines = x, top - h, 1
        for i, label in enumerate(labels):
            text = _fit(label, font, size, max_w - 8)
            w = pdfmetrics.stringWidth(text, font, size) + 8
            if cursor_x + w > x + max_w and cursor_x > x:
                cursor_x, cursor_y, lines = x, cursor_y - h - 2, lines + 1
            if lines > 3:
                c.setFont(_FONTS["mono"], 6.5)
                c.setFillColor(MUTED_STRONG)
                c.drawString(x, cursor_y + 3, f"+{len(labels) - i} more")
                return
            c.setFillColor(_tint(self.chip_color, 0.12))
            c.setStrokeColor(_tint(self.chip_color, 0.45))
            c.setLineWidth(0.5)
            c.roundRect(cursor_x, cursor_y, w, h, 3, stroke=1, fill=1)
            c.setFont(font, size)
            c.setFillColor(TEXT)
            c.drawString(cursor_x + 4, cursor_y + 3.2, text)
            cursor_x += w + 3


class _TimelineChart(Flowable):
    """Delivery roadmap as a week-by-week Gantt strip: [(name, start, end)]."""

    ROW_H = 18

    def __init__(self, phases, width, total_weeks):
        super().__init__()
        self.phases, self.total = phases, max(1, total_weeks)
        self.width, self.height = width, len(phases) * self.ROW_H + 16

    def draw(self):
        c = self.canv
        label_w = 128
        track_w = self.width - label_w
        unit = track_w / self.total
        axis_y = 8
        tick = max(1, round(self.total / 12))
        c.setLineWidth(0.5)
        for week in range(0, self.total + 1, tick):
            x = label_w + week * unit
            c.setStrokeColor(BORDER)
            c.line(x, axis_y + 4, x, self.height)
            c.setFont(_FONTS["mono"], 6.3)
            c.setFillColor(MUTED)
            c.drawCentredString(x, 0, f"W{week}" if week else "0")
        for i, (name, start, end) in enumerate(self.phases):
            y = self.height - (i + 1) * self.ROW_H + 4
            c.setFont(_FONTS["sans_bold"], 7.3)
            c.setFillColor(TEXT)
            c.drawString(0, y + 2.5, _fit(name, _FONTS["sans_bold"], 7.3, label_w - 8))
            x0 = label_w + (start - 1) * unit
            bar_w = max(6, (end - start + 1) * unit - 2)
            c.setFillColor(INFO)
            c.roundRect(x0 + 1, y, bar_w, 10, 3, stroke=0, fill=1)
            weeks = end - start + 1
            text = f"{weeks} wk" + ("s" if weeks != 1 else "")
            c.setFont(_FONTS["mono_bold"], 6.3)
            if pdfmetrics.stringWidth(text, _FONTS["mono_bold"], 6.3) + 8 < bar_w:
                c.setFillColor(PANEL)
                c.drawString(x0 + 5, y + 3, text)
            else:
                c.setFillColor(TEXT)
                c.drawString(x0 + bar_w + 4, y + 3, text)


def _chart_card(title, caption, chart, s):
    """A chart in the standard panel: mono label, caption, then the chart."""
    content = [_label_row(title, s), Spacer(1, 3)]
    if caption:
        content += [Paragraph(_e(caption), s["label"]), Spacer(1, 8)]
    content.append(chart)
    return KeepTogether([_card(content, padding=14), Spacer(1, 10)])


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

    def add(self, title, estimate=False, keep_with=120):
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
        self.story.append(CondPageBreak(keep_with))
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


def _confidence(story, d, s):
    """Evidence confidence breakdown - the same metrics as
    ConfidenceDashboard.jsx, drawn as bars on one 0-100% scale."""
    conf = d.get("confidence") or {}
    rows = []

    def add(label, value):
        if isinstance(value, (int, float)):
            rows.append((label, max(0.0, min(100.0, float(value))), _tier_color(value)))

    add("Source coverage", (conf.get("sourceCoverage") or {}).get("percentage"))
    add("Cross-source agreement", (conf.get("crossSourceAgreement") or {}).get("percentage"))
    add("Direct evidence", (conf.get("directEvidenceRatio") or {}).get("percentage"))
    if isinstance(conf.get("averageRelevance"), (int, float)):
        add("Average relevance", conf["averageRelevance"] * 100)
    recency = conf.get("sourceRecency") or {}
    if recency.get("totalSources"):
        add("Dated sources", recency.get("sourcesWithKnownDate", 0) / recency["totalSources"] * 100)
    if not rows:
        return
    overall = conf.get("percentage")
    inner = CONTENT_W - 28
    bars = _HBarChart(rows, inner - 120 if isinstance(overall, (int, float)) else inner)
    if isinstance(overall, (int, float)):
        headline = [
            Paragraph(f"{overall:.0f}%", ParagraphStyle("ConfOverall", parent=s["stat"], fontSize=30, leading=32,
                                                          textColor=_tier_color(overall))),
            Spacer(1, 3), Paragraph("OVERALL", s["stat_label"]),
        ]
        if conf.get("label"):
            headline.append(Paragraph(_e(conf["label"]), s["stat_sub"]))
        body = Table([[headline, bars]], colWidths=[120, inner - 120])
        body.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEAFTER", (0, 0), (0, -1), 0.5, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 12),
            ("LEFTPADDING", (1, 0), (1, -1), 14), ("RIGHTPADDING", (1, 0), (1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        body = bars
    story.append(Spacer(1, 12))
    story.append(_chart_card(
        "Evidence confidence",
        "How strong the evidence behind this report is - not a guarantee the business will succeed.",
        body, s,
    ))


def _market(story, d, s, sections):
    market_opp = d.get("marketOpportunity") or {}
    if not market_opp:
        return
    sections.add("Market size & growth")
    verdict = d.get("verdict") or {}
    opp_score = market_opp.get("opportunityScore", (d.get("opportunityScore") or {}).get("score"))
    # Older reports can still carry raw "[src-N]" markers in marketSize.
    size = extract_inline_citations(market_opp.get("marketSize") or "Emerging sector")[0]
    facts = [("Estimated TAM / SAM", size), ("CAGR", _extract_cagr(market_opp, size))]
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


_CLASSIFICATION_SHORT = {"direct": "Direct rival", "indirect": "Indirect rival", "unknown": "Unclear"}
_CLASSIFICATION_COLOR = {"direct": DANGER, "indirect": WARNING, "unknown": MUTED_STRONG}


def _competitors(story, d, s, sections):
    data = d.get("competitors") or {}
    comp_list = [c for c in data.get("competitors") or [] if isinstance(c, dict)]
    if not comp_list:
        return
    sections.add("Competitor landscape & positioning")
    # Classification (direct/indirect rival) comes from the LLM discovery
    # pass (competitor_agent._discover_with_llm) and is "unknown" for a
    # name NER found on its own - shown either way, as "Unclear", rather
    # than dropping the whole column whenever any competitor lacks it.
    def classification_cell(c):
        key = c.get("classification") or "unknown"
        return Paragraph(_e(_CLASSIFICATION_SHORT.get(key, "Unclear")),
                         ParagraphStyle("Class", parent=s["cell_bold"], textColor=_CLASSIFICATION_COLOR.get(key, MUTED_STRONG)))

    rows = [["Competitor", "Type", "Pricing", "Feature breadth"]]
    for c in comp_list[:8]:
        rows.append([
            Paragraph(_e(c.get("name")), s["cell_bold"]),
            classification_cell(c),
            Paragraph(_e(c.get("pricing") or c.get("estimatedPrice") or c.get("priceBucket") or "unknown"), s["cell"]),
            Paragraph(_e(c.get("featureBreadth") or "unknown"), s["cell"]),
        ])
    story.append(_data_table(rows, [CONTENT_W - 340, 90, 130, 120], s))

    # Direct rivals carry a stated weakness once profiled - surface it as
    # the "so what" a bare classification label doesn't give.
    direct_weaknesses = [(c.get("name"), c["weaknesses"][0]) for c in comp_list[:8]
                          if c.get("classification") == "direct" and c.get("weaknesses")]
    if direct_weaknesses:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Key weaknesses of direct rivals", s["label"]))
        story.append(Spacer(1, 3))
        indented = ParagraphStyle("WeaknessBullet", parent=s["bullet"], leftIndent=10)
        for name, weakness in direct_weaknesses:
            dot = f'<bullet><font color="{_hex(DANGER)}" size="6">●</font></bullet>'
            story.append(Paragraph(f"{dot}<b>{_e(name)}:</b> {_e(weakness)}", indented))

    # Positioning snapshot - same price x breadth grid as CompetitorAnalysis.jsx.
    price_rows = [("high", "High price"), ("mid", "Mid price"), ("low", "Low price")]
    breadth_cols = [("narrow", "Narrow"), ("moderate", "Moderate"), ("broad", "Broad")]
    cells: Dict[tuple, List[str]] = {}
    for c in comp_list:
        price = c.get("estimatedPrice") if c.get("estimatedPrice") in dict(price_rows) else c.get("priceBucket")
        breadth = c.get("featureBreadth")
        if price in dict(price_rows) and breadth in dict(breadth_cols):
            cells.setdefault((price, breadth), []).append(str(c.get("name") or "Unnamed"))
    if cells:
        story.append(Spacer(1, 10))
        story.append(_chart_card(
            "Positioning snapshot",
            "Approximate placement by price and feature breadth, pattern-matched from source text.",
            _MatrixChart(CONTENT_W - 28, price_rows, breadth_cols, cells, lambda r, c: SURFACE,
                         "Feature breadth", "Price", cell_h=40),
            s,
        ))


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

        levels = [("high", "High"), ("medium", "Medium"), ("low", "Low")]
        rank = {"low": 0, "medium": 1, "high": 2}
        cells: Dict[tuple, List[str]] = {}
        for i, r in enumerate(risks, 1):
            sev, lik = str(r.get("severity") or "").lower(), str(r.get("likelihood") or "").lower()
            if sev in rank and lik in rank:
                cells.setdefault((sev, lik), []).append(f"R{i}")

        def heat(sev, lik):
            # One hue, stronger toward high severity x high likelihood.
            return _tint(DANGER, 0.05 + 0.07 * (rank[sev] + rank[lik]))

        story.append(Spacer(1, 4))
        if cells:
            story.append(_chart_card(
                "Risk matrix",
                "Each risk (R1, R2, ...) placed by severity and likelihood - top right needs attention first.",
                _MatrixChart(CONTENT_W - 28, levels, list(reversed(levels)), cells, heat,
                             "Likelihood", "Severity", chip_color=DANGER, cell_h=34),
                s,
            ))
        story.append(Paragraph("Key risks", s["h3"]))
        story.append(Spacer(1, 6))
        rows = [["Risk", "Severity", "Likelihood", "Mitigation"]]
        for i, r in enumerate(risks, 1):
            rows.append([Paragraph(f'<font name="{_FONTS["mono_bold"]}" color="{_hex(DANGER)}">R{i}&nbsp;&nbsp;</font>{_e(r.get("risk"))}', s["cell"]),
                         level(r.get("severity")), level(r.get("likelihood")),
                         Paragraph(_e(r.get("mitigation") or "—"), s["cell"])])
        story.append(_data_table(rows, [180, 58, 62, CONTENT_W - 300], s))


def _voice_of_market(story, d, s, sections):
    market_opportunity = d.get("marketOpportunity") or {}
    quotes = [q for q in market_opportunity.get("voiceOfMarket") or []
              if isinstance(q, dict) and q.get("quote")]
    if not quotes:
        return
    sections.add("Voice of the market")
    summary = market_opportunity.get("voiceOfMarketSummary") or {}
    counts = summary.get("dimensionCounts") or {}
    parts = [f"{count} {dimension.lower()}{'' if count == 1 else 's'}"
             for dimension, count in counts.items() if count]
    if parts:
        line = " · ".join(parts)
        if summary.get("sourcesScanned"):
            line += f" found across {summary['sourcesScanned']} sources scanned"
        story.append(Paragraph(_e(line), s["label"]))
        story.append(Spacer(1, 6))
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
    # The radar card is tall - keep the heading on the same page as it.
    sections.add("Market viability & dynamics", keep_with=360)
    axes = []
    for x in dims:
        try:
            axes.append((x.get("name") or "Axis", max(0.0, min(5.0, float(x.get("score"))))))
        except (TypeError, ValueError):
            continue
    if len(axes) >= 3:
        story.append(_chart_card("Viability profile", "Each axis scored 0-5; a larger shape means a stronger market.",
                                 _RadarChart(axes, CONTENT_W - 28), s))
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
    spans = []
    start = 1
    for phase in phases:
        try:
            weeks = max(1, int(phase.get("durationWeeks") or 1))
        except (TypeError, ValueError):
            weeks = 1
        spans.append((str(phase.get("phaseName") or "Phase"), start, start + weeks - 1))
        start += weeks
    story.append(_chart_card("Timeline", f"{spans[-1][2]} weeks end to end, one bar per phase.",
                             _TimelineChart(spans, CONTENT_W - 28, spans[-1][2]), s))
    rows = [["Weeks", "Phase", "Deliverables", "Exit gate"]]
    for phase, (_, start, end) in zip(phases, spans):
        rows.append([
            Paragraph(f"{start}&ndash;{end}" if end > start else str(start),
                      ParagraphStyle("Weeks", parent=s["cell_bold"], fontName=_FONTS["mono_bold"], textColor=ACCENT)),
            Paragraph(_e(phase.get("phaseName")), s["cell_bold"]),
            _bullets(phase.get("coreDeliverables") or [], s, color=INFO) or Paragraph("—", s["cell"]),
            _bullets(phase.get("exitGateMilestones") or [], s, color=SUCCESS) or Paragraph("—", s["cell"]),
        ])
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


_FIT_COLOR = {"high": SUCCESS, "medium": ACCENT, "low": MUTED_STRONG}


def _gtm_strategy(story, d, s, sections):
    gtm = d.get("gtm") or {}
    positioning = gtm.get("positioning")
    channels = [c for c in gtm.get("channels") or [] if isinstance(c, dict) and c.get("text")]
    early_approach = gtm.get("earlyCustomerApproach")
    if not positioning and not channels and not early_approach:
        return
    sections.add("Go-to-market strategy")
    if positioning:
        story.append(_card([Paragraph("POSITIONING", s["label"]), Spacer(1, 4),
                            Paragraph(_e(extract_inline_citations(positioning)[0]), s["body"])]))
        story.append(Spacer(1, 8))
    if channels:
        story.append(Paragraph("Acquisition channels", s["h3"]))
        story.append(Spacer(1, 6))
        for channel in channels:
            fit = channel.get("fitScore")
            badge = _pill(f"{fit} fit", _FIT_COLOR.get(fit, MUTED_STRONG), s) if fit else ""
            text = extract_inline_citations(channel["text"])[0]
            tactics = [t for t in channel.get("tactics") or [] if str(t or "").strip()]
            content = [Table([[Paragraph(_e(text), s["cell_bold"]), badge]],
                             colWidths=[CONTENT_W - 28 - (badge.wrap(CONTENT_W, 20)[0] if badge else 0),
                                        badge.wrap(CONTENT_W, 20)[0] if badge else 0],
                             style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])]
            if tactics:
                content += [Spacer(1, 5)] + _bullets(tactics, s, color=INFO)
            story.append(KeepTogether(_card(content, padding=12)))
            story.append(Spacer(1, 8))
    if early_approach:
        story.append(_card([Paragraph("EARLY CUSTOMER APPROACH", s["label"]), Spacer(1, 4),
                            Paragraph(_e(extract_inline_citations(early_approach)[0]), s["body"])]))


def _revenue_models(story, d, s, sections):
    models = [m for m in (d.get("revenueModels") or {}).get("models") or [] if isinstance(m, dict) and m.get("name")]
    if not models:
        return
    sections.add("Revenue model options")
    for model in models:
        fit = model.get("fit")
        badge = _pill(f"{fit} fit", _FIT_COLOR.get(fit, MUTED_STRONG), s) if fit else ""
        title = [Paragraph(_e(model["name"]), s["h3"])]
        if model.get("pricingRange"):
            title += [Spacer(1, 2), Paragraph(_e(model["pricingRange"]), s["label"])]
        bw = badge.wrap(CONTENT_W, 20)[0] if badge else 0
        top = Table([[title, badge]], colWidths=[CONTENT_W - 28 - bw, bw],
                    style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])
        content = [top]
        if model.get("rationale"):
            content += [Spacer(1, 6), Paragraph(_e(model["rationale"]), s["body"])]
        companies = [c for c in model.get("exampleCompanies") or [] if str(c or "").strip()]
        if companies:
            content += [Spacer(1, 6), Paragraph(
                f'<font name="{_FONTS["mono_bold"]}" size="7" color="{_hex(MUTED)}">USED BY&nbsp;&nbsp;</font>{_e(", ".join(companies))}',
                s["body_muted"])]
        if model.get("tradeoffs"):
            content += [Spacer(1, 6), Paragraph(
                f'<font name="{_FONTS["mono_bold"]}" size="7" color="{_hex(WARNING)}">TRADEOFF&nbsp;&nbsp;</font>{_e(model["tradeoffs"])}',
                s["body_muted"])]
        story.append(KeepTogether(_card(content, padding=14)))
        story.append(Spacer(1, 8))


def build_story(dossier_data: Dict[str, Any], generated: str) -> list:
    """The report's flowables in reading order: idea context, verdict,
    summary + KPI strip, evidence confidence, then the numbered analysis sections (each skipped
    when its data is missing, e.g. older sessions)."""
    _register_fonts()
    d = dossier_data or {}
    s = _styles()
    story: list = []
    _cover(story, d, s, _concept_title(d.get("idea") or d.get("ideaTitle") or ""), generated)
    _verdict(story, d, s)
    _summary_and_stats(story, d, s)
    _confidence(story, d, s)

    sections = _Sections(story, s)
    _market(story, d, s, sections)
    _competitors(story, d, s, sections)
    _swot(story, d, s, sections)
    _voice_of_market(story, d, s, sections)
    _viability(story, d, s, sections)
    _wedges(story, d, s, sections)
    _roadmap(story, d, s, sections)
    _economics(story, d, s, sections)
    _gtm_strategy(story, d, s, sections)
    _revenue_models(story, d, s, sections)
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
