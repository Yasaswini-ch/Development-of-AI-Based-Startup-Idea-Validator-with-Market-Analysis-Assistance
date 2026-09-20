"""Email delivery for validation reports that take longer than the
synchronous request threshold to finish (see main.py's async path).

Uses Resend's HTTP API directly via urllib - consistent with tools.py's
existing pattern of plain urllib calls rather than adding a new SDK
dependency for one HTTP POST. Requires RESEND_API_KEY; if it isn't set,
send_report_email logs a warning and returns False instead of raising, the
same "degrade, don't crash" pattern used everywhere else a key is optional
(see llm.py, tools.py). RESEND_FROM_EMAIL controls the sender address and
must be a domain verified in the Resend account - Resend rejects sends
from unverified domains, so this isn't optional once RESEND_API_KEY is set.
"""

import base64
import json
import logging
import os
import re
import urllib.request

logger = logging.getLogger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(address: str) -> bool:
    return bool(_EMAIL_PATTERN.match(address.strip()))


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _section(title: str, body_html: str) -> str:
    return f'<h2 style="font-family:sans-serif;font-size:16px;margin:24px 0 8px;">{_escape(title)}</h2>{body_html}'


def _build_report_html(idea: str, response: dict) -> str:
    """A plain, readable HTML summary - not the full structured report
    export from docs/unique-features-plan.md, just enough for someone to
    read the outcome in their inbox and click through to the app for detail.
    """
    parts = [
        f'<p style="font-family:sans-serif;font-size:14px;color:#555;">Your validation report for:</p>'
        f'<p style="font-family:sans-serif;font-size:16px;font-weight:600;">{_escape(idea)}</p>'
    ]

    summary = response.get("summary")
    if summary:
        parts.append(_section("Summary", f'<p style="font-family:sans-serif;font-size:14px;">{_escape(summary)}</p>'))

    market = response.get("marketOpportunity")
    if market and market.get("marketSize"):
        parts.append(
            _section("Market opportunity", f'<p style="font-family:sans-serif;font-size:14px;">{_escape(market["marketSize"])}</p>')
        )

    competitors = (response.get("competitors") or {}).get("competitors") or []
    if competitors:
        items = "".join(f'<li style="font-family:sans-serif;font-size:14px;">{_escape(c.get("name", ""))}</li>' for c in competitors)
        parts.append(_section("Competitors identified", f"<ul>{items}</ul>"))

    swot = response.get("swot")
    if swot and swot.get("strengths"):
        # strengths items are {"text", "sourceIds"} objects (see
        # docs/unique-features-plan.md §5.1) - str() covers any
        # older/plain-string shape too.
        strength_texts = [s.get("text", "") if isinstance(s, dict) else str(s) for s in swot["strengths"]]
        items = "".join(f'<li style="font-family:sans-serif;font-size:14px;">{_escape(s)}</li>' for s in strength_texts)
        parts.append(_section("Strengths", f"<ul>{items}</ul>"))

    errors = response.get("errors") or {}
    failed_sections = [name for name, message in errors.items() if message]
    if failed_sections:
        parts.append(
            _section(
                "Note",
                f'<p style="font-family:sans-serif;font-size:13px;color:#888;">'
                f"The following sections could not be generated this run: {_escape(', '.join(failed_sections))}."
                f"</p>",
            )
        )

    parts.append(
        '<p style="font-family:sans-serif;font-size:13px;color:#888;margin-top:24px;">'
        "Open Affinity to see the full report with sources, MVP recommendations, and go-to-market strategy."
        "</p>"
    )
    return "".join(parts)


def _build_report_text(idea: str, report: dict) -> str:
    """Plain-text companion to the HTML body - rule 10 in
    docs/unique-features-plan.md §7 requires both, for mail clients/
    screen readers that don't render HTML.
    """
    lines = [f"Your Affinity validation report for: {idea}", ""]

    idea_summary = report.get("ideaSummary") or {}
    if idea_summary.get("summary"):
        lines += ["Summary:", idea_summary["summary"], ""]

    market = report.get("marketOpportunity")
    if market and market.get("marketSize"):
        lines += ["Market opportunity:", market["marketSize"], ""]

    lines.append("Open Affinity to see the full report with sources, MVP recommendations, and go-to-market strategy.")
    return "\n".join(lines)


def send_canonical_report_email(to_email: str, report: dict, pdf_bytes: bytes) -> bool:
    """Send the Track D canonical report object (report_assembler.py) as a
    PDF attachment, with a plain-text and HTML body summary. Distinct from
    send_report_email above, which sends the smaller inline-HTML-only
    summary used by the long-running-validation async path and predates
    the canonical report object existing at all.

    Same "never crash the caller, return False" contract as
    send_report_email: a failed/misconfigured email must not be confused
    with a failure to assemble or export the report itself.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set - skipping report email to %s", to_email)
        return False

    from_email = os.environ.get("RESEND_FROM_EMAIL", "Affinity <onboarding@resend.dev>")

    if not is_valid_email(to_email):
        logger.warning("Refusing to send report email to invalid address")
        return False

    idea_summary = report.get("ideaSummary") or {}
    idea = idea_summary.get("idea", "")
    # _build_report_html/_build_report_text expect the /validate response
    # shape (top-level "summary"/"errors") - the canonical report nests
    # summary under ideaSummary and calls the same thing sectionErrors, so
    # adapt rather than duplicate the HTML-building logic for this shape.
    html_input = {**report, "summary": idea_summary.get("summary", ""), "errors": report.get("sectionErrors")}

    payload = json.dumps(
        {
            "from": from_email,
            "to": [to_email],
            "subject": "Your Affinity validation report is ready",
            "html": _build_report_html(idea, html_input),
            "text": _build_report_text(idea, report),
            "attachments": [
                {
                    "filename": f"Affinity_Report_{report.get('reportId', 'report')}.pdf",
                    "content": base64.b64encode(pdf_bytes).decode("ascii"),
                }
            ],
        }
    ).encode()

    request = urllib.request.Request(
        _RESEND_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        # Never log the recipient address or report contents (see
        # docs/unique-features-plan.md §7 email rules) - just that a send
        # failed, same as send_report_email above.
        logger.exception("Failed to send canonical report email")
        return False


def send_report_email(to_email: str, idea: str, response: dict) -> bool:
    """Send the finished validation report by email. Returns True only on a
    confirmed Resend acceptance; False on any missing config or delivery
    failure - callers should log/store that outcome, not raise on it, since
    a failed email must never take down an otherwise-successful validation
    run (the result is still available in the job store either way).
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set - skipping report email to %s", to_email)
        return False

    from_email = os.environ.get("RESEND_FROM_EMAIL", "Affinity <onboarding@resend.dev>")

    if not is_valid_email(to_email):
        logger.warning("Refusing to send report email to invalid address")
        return False

    payload = json.dumps(
        {
            "from": from_email,
            "to": [to_email],
            "subject": "Your Affinity validation report is ready",
            "html": _build_report_html(idea, response),
        }
    ).encode()

    request = urllib.request.Request(
        _RESEND_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        logger.exception("Failed to send report email")
        return False
