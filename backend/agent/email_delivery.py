"""Email delivery for validation reports that take longer than the
synchronous request threshold to finish (see main.py's async path).

Sends via SendGrid's HTTP API (urllib, standard library - no new
dependency, same pattern as tools.py's other HTTP calls), authenticated
with SENDGRID_API_KEY and sent from SENDGRID_FROM_EMAIL (verified once via
SendGrid's "Single Sender Verification" - no domain needed, just click the
confirmation link SendGrid emails to that address). Once verified, that
single sender can email any recipient.

Second transport tried here, in order: Resend's HTTP API (dropped - its
free/sandbox sender can only deliver to the account owner's own address
until a domain is verified, and this project has no domain), then Gmail
SMTP (dropped - confirmed live that Render's free-tier web services block
outbound SMTP ports 587/465/25 entirely, "OSError: [Errno 101] Network is
unreachable", a network-level restriction with no code-side fix). SendGrid
over HTTPS (port 443) hits neither problem: not domain-gated for arbitrary
recipients, and not a port SMTP-blocking hosts filter.

If either env var is missing, send_report_email logs a warning and returns
False instead of raising, the same "degrade, don't crash" pattern used
everywhere else a credential is optional (see llm.py, tools.py).
"""

import json
import logging
import os
import re
import urllib.request

from . import events
from .structured_output import extract_inline_citations

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"

# Same lesson as email_delivery.py's earlier Resend integration and
# tools.py's Hacker News call: a bare urllib.request default User-Agent
# ("Python-urllib/3.x") gets blocked as a bot signature by some APIs'
# Cloudflare fronting - set a real one preemptively rather than
# rediscovering the same 403 again.
_REQUEST_HEADERS_BASE = {"User-Agent": "StartupIdeaValidator/1.0", "Content-Type": "application/json"}


def is_valid_email(address: str) -> bool:
    return bool(_EMAIL_PATTERN.match(address.strip()))


# Same palette as frontend/src/index.css's @theme block - kept as literal
# hex values here (not shared/imported) since an email has to be a single
# self-contained HTML document with inline styles; email clients don't
# load external stylesheets or CSS custom properties reliably.
_C_SURFACE = "#f6f2ec"
_C_PANEL = "#fffdfa"
_C_BORDER = "#e6dfd3"
_C_TEXT = "#262220"
_C_MUTED = "#8a8178"
_C_ACCENT = "#e0654b"
_C_ACCENT_SOFT = "#fbe8e3"

# Web fonts (Fraunces/JetBrains Mono/Inter) aren't reliably available in
# email clients - Georgia and Helvetica are the closest widely-supported
# serif/sans-serif approximation of the app's own serif-headline /
# sans-body pairing.
_F_SERIF = "Georgia, 'Times New Roman', serif"
_F_SANS = "Helvetica, Arial, sans-serif"
_F_MONO = "'Courier New', Courier, monospace"

_LEVEL_COLORS = {
    "high": "#c8543c",
    "medium": "#b8863a",
    "low": _C_MUTED,
    "unknown": _C_MUTED,
}


def _escape(text) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _claim_text(item) -> str:
    """A claim is {"text", "sourceIds"} (see docs/unique-features-plan.md
    §5.1) in every current section - str() covers any older/plain-string
    shape so this never crashes on a stale cached response.
    """
    return item.get("text", "") if isinstance(item, dict) else str(item)


def _p(text: str, *, size: int = 14, color: str = _C_TEXT, margin: str = "0") -> str:
    return f'<p style="font-family:{_F_SANS};font-size:{size}px;line-height:1.6;color:{color};margin:{margin};">{_escape(text)}</p>'


def _bullet_list(items: list[str]) -> str:
    if not items:
        return ""
    rows = "".join(
        f'<tr><td style="padding:4px 0;vertical-align:top;width:14px;">'
        f'<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:{_C_ACCENT};margin-top:8px;"></span></td>'
        f'<td style="padding:4px 0;font-family:{_F_SANS};font-size:13px;line-height:1.6;color:{_C_TEXT};">{_escape(item)}</td></tr>'
        for item in items
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tbody>{rows}</tbody></table>'


def _badge(label: str, value: str) -> str:
    color = _LEVEL_COLORS.get(value, _C_MUTED)
    return (
        f'<span style="display:inline-block;font-family:{_F_MONO};font-size:10px;text-transform:uppercase;'
        f'letter-spacing:0.05em;color:{color};border:1px solid {_C_BORDER};border-radius:12px;'
        f'padding:2px 8px;margin:0 6px 6px 0;">{_escape(label)}: {_escape(value)}</span>'
    )


def _section(title: str, body_html: str, *, note: str | None = None) -> str:
    if not body_html:
        return ""
    note_html = f'<p style="font-family:{_F_SANS};font-size:12px;color:{_C_MUTED};margin:0 0 10px;">{_escape(note)}</p>' if note else ""
    return (
        f'<tr><td style="padding:22px 28px;border-top:1px solid {_C_BORDER};">'
        f'<p style="font-family:{_F_MONO};font-size:11px;text-transform:uppercase;letter-spacing:0.08em;'
        f'color:{_C_ACCENT};margin:0 0 10px;">{_escape(title)}</p>'
        f'{note_html}{body_html}</td></tr>'
    )


def _stat_box(value: str, label: str) -> str:
    return (
        f'<td width="33%" style="padding:14px 10px;text-align:center;border-right:1px solid {_C_BORDER};">'
        f'<p style="font-family:{_F_SERIF};font-size:26px;color:{_C_ACCENT};margin:0;">{_escape(value)}</p>'
        f'<p style="font-family:{_F_MONO};font-size:9px;text-transform:uppercase;letter-spacing:0.06em;'
        f'color:{_C_MUTED};margin:2px 0 0;">{_escape(label)}</p></td>'
    )


def _tier_html(tier: dict | None, label: str) -> str | None:
    if not isinstance(tier, dict) or not tier.get("text"):
        return None
    return f'<p style="font-family:{_F_SANS};font-size:13px;color:{_C_TEXT};margin:0 0 4px;"><strong>{label}:</strong> {_escape(tier["text"])}</p>'


def _build_report_html(idea: str, response: dict, report_url: str | None = None) -> str:
    """The full validation report as a single self-contained, inline-
    styled HTML document matching the app's own visual identity (see
    frontend/src/index.css's palette) - table-based layout throughout
    since email clients (Outlook especially) don't reliably support
    flexbox/grid, only tables and inline styles.

    Every section is optional and silently omitted when its data is
    absent/None - the same "don't show a fabricated-looking blank" rule
    the frontend components already follow, not new behavior here.
    """
    market = response.get("marketOpportunity") or {}
    competitors = (response.get("competitors") or {}).get("competitors") or []
    swot = response.get("swot") or {}
    mvp = (response.get("mvp") or {}).get("features") or []
    gtm = response.get("gtm") or {}
    viability = response.get("marketViability") or {}
    contradictions = response.get("contradictions") or []

    sections = []

    # --- Header banner ---
    sections.append(
        f'<tr><td style="background:{_C_ACCENT};padding:28px;text-align:center;">'
        f'{_logo_html()}'
        f'<p style="font-family:{_F_MONO};font-size:11px;text-transform:uppercase;letter-spacing:0.15em;color:#fff;opacity:0.85;margin:0 0 6px;">Affinity</p>'
        f'<p style="font-family:{_F_SERIF};font-size:20px;color:#fff;margin:0;">Your validation report is ready</p>'
        f'</td></tr>'
    )

    # --- Idea + summary ---
    idea_body = f'<p style="font-family:{_F_SERIF};font-size:18px;color:{_C_TEXT};margin:0 0 10px;">{_escape(idea)}</p>'
    if response.get("summary"):
        idea_body += _p(response["summary"], size=13, color=_C_MUTED)
    sections.append(_section("Startup idea", idea_body))

    # --- Headline stats ---
    stats = []
    if isinstance(market.get("opportunityScore"), (int, float)) and market["opportunityScore"] > 0:
        stats.append(_stat_box(str(market["opportunityScore"]), "Opportunity score"))
    if viability.get("score") is not None:
        stats.append(_stat_box(str(viability["score"]), viability.get("label", "Viability")))
    confidence = response.get("confidence") or {}
    if confidence.get("percentage") is not None:
        stats.append(_stat_box(f'{confidence["percentage"]}%', "Confidence"))
    if stats:
        stats[-1] = stats[-1].replace(f"border-right:1px solid {_C_BORDER};", "")
        sections.append(
            f'<tr><td style="padding:0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tbody><tr>{"".join(stats)}</tr></tbody></table></td></tr>'
        )

    # --- Market opportunity: size + TAM/SAM/SOM + trends ---
    market_body = ""
    if market.get("marketSize"):
        market_body += _p(extract_inline_citations(market["marketSize"])[0])
    tiers = [t for t in (_tier_html(market.get("tam"), "TAM"), _tier_html(market.get("sam"), "SAM"), _tier_html(market.get("som"), "SOM")) if t]
    if tiers:
        market_body += f'<div style="margin-top:10px;">{"".join(tiers)}</div>'
    trends = [_claim_text(t) for t in (market.get("trends") or [])]
    if trends:
        market_body += f'<p style="font-family:{_F_MONO};font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:{_C_MUTED};margin:14px 0 6px;">Trends</p>{_bullet_list(trends)}'
    sections.append(_section("Market opportunity", market_body, note="TAM/SAM/SOM are only shown when a source explicitly supports that figure."))

    # --- Competitors ---
    if competitors:
        rows = []
        for c in competitors:
            badges = "".join(_badge(l, c.get(k, "unknown")) for l, k in (("Price", "estimatedPrice"), ("Breadth", "featureBreadth")) if c.get(k, "unknown") != "unknown")
            rows.append(
                f'<div style="padding:10px 0;border-top:1px solid {_C_BORDER};">'
                f'<p style="font-family:{_F_SANS};font-size:13px;font-weight:bold;color:{_C_TEXT};margin:0 0 3px;">{_escape(c.get("name", ""))}</p>'
                f'<p style="font-family:{_F_SANS};font-size:12px;color:{_C_MUTED};margin:0 0 6px;">{_escape(c.get("offering", ""))}</p>'
                f'{badges}</div>'
            )
        sections.append(_section("Competitors identified", "".join(rows)))

    # --- SWOT ---
    swot_quadrants = [
        ("Strengths", swot.get("strengths")),
        ("Weaknesses", swot.get("weaknesses")),
        ("Opportunities", swot.get("opportunities")),
        ("Threats", swot.get("threats")),
    ]
    swot_body = ""
    for label, items in swot_quadrants:
        texts = [_claim_text(i) for i in (items or [])]
        if texts:
            swot_body += f'<p style="font-family:{_F_MONO};font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:{_C_MUTED};margin:12px 0 6px;">{_escape(label)}</p>{_bullet_list(texts)}'
    risks = swot.get("risks") or []
    if risks:
        swot_body += f'<p style="font-family:{_F_MONO};font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:{_C_MUTED};margin:14px 0 6px;">Key risks</p>'
        for risk in risks:
            swot_body += (
                f'<div style="padding:6px 0;">{_p(risk.get("risk", ""), size=13)}'
                f'{_badge("Severity", risk.get("severity", "unknown"))}{_badge("Likelihood", risk.get("likelihood", "unknown"))}</div>'
            )
    sections.append(_section("SWOT & risks", swot_body))

    # --- MVP ---
    if mvp:
        rows = "".join(
            f'<div style="padding:8px 0;border-top:1px solid {_C_BORDER};">'
            f'<p style="font-family:{_F_SANS};font-size:13px;font-weight:bold;color:{_C_TEXT};margin:0 0 3px;">{_escape(f.get("feature", ""))}</p>'
            f'<p style="font-family:{_F_SANS};font-size:12px;color:{_C_MUTED};margin:0 0 6px;">{_escape(f.get("rationale", ""))}</p>'
            f'{_badge("Impact", f.get("impact", "unknown"))}{_badge("Effort", f.get("effort", "unknown"))}</div>'
            for f in mvp
        )
        sections.append(_section("MVP recommendations", rows))

    # --- GTM ---
    gtm_body = ""
    if gtm.get("positioning"):
        gtm_body += _p(gtm["positioning"])
    channels = [_claim_text(c) for c in (gtm.get("channels") or [])]
    if channels:
        gtm_body += f'<p style="font-family:{_F_MONO};font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:{_C_MUTED};margin:12px 0 6px;">Priority channels</p>{_bullet_list(channels)}'
    if gtm.get("earlyCustomerApproach"):
        gtm_body += f'<p style="font-family:{_F_MONO};font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:{_C_MUTED};margin:12px 0 6px;">First customers</p>{_p(gtm["earlyCustomerApproach"])}'
    sections.append(_section("Go-to-market strategy", gtm_body))

    # --- Contradictions ---
    if contradictions:
        body = "".join(
            f'<div style="padding:8px 0;border-top:1px solid {_C_BORDER};">'
            f'{_p(c.get("summary", ""), size=13)}</div>'
            for c in contradictions
        )
        sections.append(
            _section(
                "Contradictions worth a second look",
                body,
                note="Heuristic tensions between sections of the analysis, not proof either side is wrong.",
            )
        )

    # --- Degraded/failed sections note ---
    errors = response.get("errors") or {}
    failed_sections = [name for name, message in errors.items() if message]
    if failed_sections:
        sections.append(
            _section(
                "Note",
                _p(f"The following sections could not be generated this run: {', '.join(failed_sections)}.", size=12, color=_C_MUTED),
            )
        )

    # --- CTA + footer ---
    cta = ""
    if report_url:
        # No accounts/login exist (see docs/unique-features-plan.md §1) - this
        # link, not a dashboard, is the only way to come back to a past
        # session from a different browser/device. Framed honestly as a
        # bookmark, not a "history" feature backed by a real account.
        cta = (
            f'<tr><td style="padding:24px 28px;text-align:center;border-top:1px solid {_C_BORDER};background:{_C_SURFACE};">'
            f'<a href="{_escape(report_url)}" style="display:inline-block;font-family:{_F_MONO};font-size:12px;'
            f'text-transform:uppercase;letter-spacing:0.05em;color:#fff;background:{_C_ACCENT};padding:12px 28px;'
            f'border-radius:24px;text-decoration:none;">View this report again</a>'
            f'<p style="font-family:{_F_SANS};font-size:11px;color:{_C_MUTED};margin:12px 0 0;">'
            "This link isn't tied to an account - anyone with it can open this report."
            f'</p></td></tr>'
        )
    sections.append(cta)
    sections.append(
        f'<tr><td style="padding:18px 28px;text-align:center;background:{_C_SURFACE};">'
        f'<p style="font-family:{_F_MONO};font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:{_C_MUTED};margin:0;">'
        "Multi-agent pipeline &middot; Live web search &middot; Sources cited throughout"
        f'</p></td></tr>'
    )

    body = "".join(s for s in sections if s)
    return (
        f'<div style="background:{_C_SURFACE};padding:24px 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;'
        f'background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:16px;overflow:hidden;">'
        f'<tbody>{body}</tbody></table></div>'
    )


def _build_report_text(idea: str, report: dict, report_url: str | None = None) -> str:
    """Plain-text companion to the HTML body - rule 10 in
    docs/unique-features-plan.md §7 requires both, for mail clients/
    screen readers that don't render HTML. Mirrors the HTML version's
    sections (market/TAM-SAM-SOM/competitors/SWOT/risks/MVP/GTM/
    contradictions), just without any styling.
    """
    idea_summary = report.get("ideaSummary") or {}
    lines = [f"AFFINITY — Your validation report for: {idea}", ""]

    if idea_summary.get("summary"):
        lines += [idea_summary["summary"], ""]

    market = report.get("marketOpportunity") or {}
    if market.get("marketSize"):
        lines += ["MARKET OPPORTUNITY", extract_inline_citations(market["marketSize"])[0]]
    for label, key in (("TAM", "tam"), ("SAM", "sam"), ("SOM", "som")):
        tier = market.get(key)
        if isinstance(tier, dict) and tier.get("text"):
            lines.append(f"  {label}: {tier['text']}")
    trends = [_claim_text(t) for t in (market.get("trends") or [])]
    if trends:
        lines.append("  Trends: " + "; ".join(trends))
    if market.get("opportunityScore"):
        lines.append(f"  Opportunity score: {market['opportunityScore']}/100")
    viability = report.get("marketViability") or {}
    if viability.get("score") is not None:
        lines.append(f"  Market viability: {viability['score']}/100 ({viability.get('label', '')})")
    lines.append("")

    competitors = (report.get("competitors") or {}).get("competitors") or []
    if competitors:
        lines.append("COMPETITORS")
        for c in competitors:
            lines.append(f"  - {c.get('name', '')}: {c.get('offering', '')}")
        lines.append("")

    swot = report.get("swot") or {}
    for label, key in (("Strengths", "strengths"), ("Weaknesses", "weaknesses"), ("Opportunities", "opportunities"), ("Threats", "threats")):
        texts = [_claim_text(i) for i in (swot.get(key) or [])]
        if texts:
            lines.append(f"SWOT - {label.upper()}")
            lines += [f"  - {t}" for t in texts]
    risks = swot.get("risks") or []
    if risks:
        lines.append("KEY RISKS")
        for risk in risks:
            lines.append(f"  - {risk.get('risk', '')} (severity: {risk.get('severity', 'unknown')}, likelihood: {risk.get('likelihood', 'unknown')})")
    if swot:
        lines.append("")

    mvp = (report.get("mvp") or {}).get("features") or []
    if mvp:
        lines.append("MVP RECOMMENDATIONS")
        for f in mvp:
            lines.append(f"  - {f.get('feature', '')} (impact: {f.get('impact', 'unknown')}, effort: {f.get('effort', 'unknown')})")
        lines.append("")

    gtm = report.get("gtm") or {}
    if gtm:
        lines.append("GO-TO-MARKET")
        if gtm.get("positioning"):
            lines.append(f"  Positioning: {gtm['positioning']}")
        channels = [_claim_text(c) for c in (gtm.get("channels") or [])]
        if channels:
            lines.append("  Channels: " + "; ".join(channels))
        if gtm.get("earlyCustomerApproach"):
            lines.append(f"  First customers: {gtm['earlyCustomerApproach']}")
        lines.append("")

    contradictions = report.get("contradictions") or []
    if contradictions:
        lines.append("CONTRADICTIONS WORTH A SECOND LOOK")
        lines += [f"  - {c.get('summary', '')}" for c in contradictions]
        lines.append("")

    lines.append("Open Affinity to see the full report with sources.")
    if report_url:
        lines += ["", f"View this report again: {report_url}", "(Not tied to an account - anyone with this link can open it.)"]
    return "\n".join(lines)


def _send_via_sendgrid(to_email: str, subject: str, html: str, text: str | None = None) -> bool:
    """Shared HTTP transport for both send_report_email and
    send_canonical_report_email below - never raises, returns False on any
    missing credential or delivery failure so a failed/misconfigured email
    is never confused with a failure to assemble the report itself (same
    contract both callers already documented under the earlier Resend/
    Gmail SMTP transports).
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    if not api_key or not from_email:
        logger.warning("SENDGRID_API_KEY/SENDGRID_FROM_EMAIL not set - skipping report email to %s", to_email)
        events.record("email_sent", detail={"outcome": "skipped_no_config"})
        return False

    if not is_valid_email(to_email):
        logger.warning("Refusing to send report email to invalid address")
        events.record("email_sent", detail={"outcome": "skipped_invalid_address"})
        return False

    payload = json.dumps(
        {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email, "name": "Affinity"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text or " "},
                {"type": "text/html", "value": html},
            ],
        }
    ).encode()

    request = urllib.request.Request(
        _SENDGRID_ENDPOINT,
        data=payload,
        method="POST",
        headers={**_REQUEST_HEADERS_BASE, "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            delivered = 200 <= resp.status < 300
            events.record("email_sent", detail={"outcome": "sent" if delivered else "failed"})
            return delivered
    except Exception:
        # Never log the recipient address or report contents (see
        # docs/unique-features-plan.md §7 email rules) - just that a send
        # failed.
        logger.exception("Failed to send report email via SendGrid")
        events.record("email_sent", detail={"outcome": "failed"})
        return False


def _logo_html() -> str:
    """The logo for the top of an email, as an <img> pointing at the public
    site. Email clients do not run scripts or load local files, so the image has
    to come from a public https address; with no https FRONTEND_ORIGIN (local
    development) nothing is shown rather than a broken image."""
    origin = (os.environ.get("FRONTEND_ORIGIN") or "").strip().rstrip("/")
    if not origin.startswith("https://"):
        return ""
    return (
        f'<img src="{_escape(origin)}/logo.png" width="44" height="44" alt="Affinity" '
        'style="display:block;margin:0 auto 10px;background:#ffffff;border-radius:22px;padding:6px;">'
    )


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Email a password-reset link. Same never-raises contract as the other
    senders. Neither the address nor the link is logged."""
    subject = "Reset your Affinity password"
    text = (
        "Someone asked to reset the password for your Affinity account.\n\n"
        f"Choose a new password here (the link works once and expires in 30 minutes):\n{reset_url}\n\n"
        "If you did not ask for this, you can ignore this email. Your password has not changed."
    )
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;color:#1f1a17">'
        '<h2 style="font-weight:600">Reset your password</h2>'
        "<p>Someone asked to reset the password for your Affinity account.</p>"
        f'<p><a href="{_escape(reset_url)}" style="display:inline-block;background:#e0654b;color:#fff;'
        'padding:10px 20px;border-radius:999px;text-decoration:none">Choose a new password</a></p>'
        '<p style="font-size:13px;color:#6b625b">The link works once and expires in 30 minutes. '
        "If you did not ask for this, ignore this email. Your password has not changed.</p></div>"
    )
    return _send_via_sendgrid(to_email, subject, html, text)


def send_canonical_report_email(to_email: str, report: dict, report_url: str | None = None) -> bool:
    """Send the Track D canonical report object (report_assembler.py) as a
    plain-text and HTML body summary. Distinct from send_report_email
    above, which sends the smaller inline-HTML-only summary used by the
    long-running-validation async path and predates the canonical report
    object existing at all.

    No longer attaches a PDF - GET /validate/{sessionId}/pdf covers direct
    PDF download from the app's own UI ("Save as PDF" button) without also
    needing to generate and email one, and the HTML/text bodies already
    carry the full report content (see _build_report_html/_build_report_text).

    report_url, when given, is a link back to GET /reports/{sessionId} the
    email body includes as a "view again" button - the closest thing to
    "history" this app has without a real login system (see
    docs/unique-features-plan.md §1: no accounts exist).

    Same "never crash the caller, return False" contract as
    send_report_email: a failed/misconfigured email must not be confused
    with a failure to assemble the report itself.
    """
    idea_summary = report.get("ideaSummary") or {}
    idea = idea_summary.get("idea", "")
    # _build_report_html/_build_report_text expect the /validate response
    # shape (top-level "summary"/"errors") - the canonical report nests
    # summary under ideaSummary and calls the same thing sectionErrors, so
    # adapt rather than duplicate the HTML-building logic for this shape.
    html_input = {**report, "summary": idea_summary.get("summary", ""), "errors": report.get("sectionErrors")}

    return _send_via_sendgrid(
        to_email,
        "Your Affinity validation report is ready",
        _build_report_html(idea, html_input, report_url),
        text=_build_report_text(idea, report, report_url),
    )


def send_report_email(to_email: str, idea: str, response: dict, report_url: str | None = None) -> bool:
    """Send the finished validation report by email. Returns True only on a
    confirmed SendGrid acceptance; False on any missing config or delivery
    failure - callers should log/store that outcome, not raise on it, since
    a failed email must never take down an otherwise-successful validation
    run (the result is still available in the job store either way).

    report_url, when given, is a link back to GET /reports/{sessionId} - see
    send_canonical_report_email's docstring for why this is the closest
    thing to "history" this app has without a real login system.
    """
    return _send_via_sendgrid(
        to_email,
        "Your Affinity validation report is ready",
        _build_report_html(idea, response, report_url),
    )
