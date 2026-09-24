"""Aggregation for GET /me/analytics - the "My Ideas" dashboard.

Replaces the frontend's previous approach (fetch GET /me/history, then
GET /reports/{id} once per session, then reduce client-side): this does
the same fan-out server-side and returns pre-aggregated numbers, which
scales better as a user's history grows and lets the dashboard show
richer breakdowns (assumption risk by category, viability dimensions,
revenue model distribution, recurring SWOT themes) without shipping every
session's full report to the browser just to compute a few numbers from it.

Reads the same session contexts GET /reports/{sessionId} does - nothing
here re-derives analysis or calls an LLM/search provider.
"""

from collections import Counter

from .session_store import get_session, list_sessions_for_user

_RISK_SEVERITIES = ("high", "medium", "low")

# Same coarse, keyword-based approach as agent/idea_category.py - bucketing
# revenue_agent.py's free-text model names (e.g. "SaaS Subscription",
# "Usage-based licensing") into a fixed set for the distribution chart is a
# "read obvious keywords" problem, not one that needs an LLM call or a
# fuzzy-clustering library.
_REVENUE_MODEL_KEYWORDS = {
    "Subscription / SaaS": ("subscription", "saas", "recurring", "membership"),
    "Freemium": ("freemium", "free tier"),
    "Usage-based": ("usage-based", "usage based", "pay-as-you-go", "metered", "per-transaction", "per transaction"),
    "One-time purchase": ("one-time", "one time", "upfront", "perpetual license"),
    "Marketplace / commission": ("marketplace", "commission", "take rate", "transaction fee"),
    "Advertising": ("advertis", "sponsor"),
}
_OTHER_REVENUE_MODEL = "Other"


def _bucket_revenue_model(name: str) -> str:
    text = (name or "").lower()
    for bucket, keywords in _REVENUE_MODEL_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return bucket
    return _OTHER_REVENUE_MODEL


def _viability_dimensions(contexts: list[dict]) -> dict:
    fields = ("marketDemand", "executionRisk", "growthVelocity", "competitionClarity", "timing")
    sums = dict.fromkeys(fields, 0)
    counts = dict.fromkeys(fields, 0)
    for context in contexts:
        viability = context.get("marketViability")
        if not isinstance(viability, dict):
            continue
        for field in fields:
            value = viability.get(field)
            if isinstance(value, (int, float)):
                sums[field] += value
                counts[field] += 1
    return {field: round(sums[field] / counts[field]) for field in fields if counts[field]}


def _assumption_risk_by_category(contexts: list[dict]) -> dict:
    tally: dict[str, Counter] = {}
    for context in contexts:
        assumptions = ((context.get("assumptions") or {}).get("assumptions")) or []
        for item in assumptions:
            if not isinstance(item, dict):
                continue
            category = item.get("category", "unknown")
            uncertainty = item.get("uncertainty", "unknown")
            tally.setdefault(category, Counter())[uncertainty] += 1
    return {category: {level: counter.get(level, 0) for level in _RISK_SEVERITIES} for category, counter in tally.items()}


def _revenue_model_distribution(contexts: list[dict]) -> list[dict]:
    counts = Counter()
    for context in contexts:
        models = ((context.get("revenueModels") or {}).get("models")) or []
        for model in models:
            if isinstance(model, dict):
                counts[_bucket_revenue_model(model.get("name", ""))] += 1
    total = sum(counts.values())
    return [
        {"model": bucket, "count": count, "percentage": round(count / total * 100) if total else 0}
        for bucket, count in counts.most_common()
    ]


def _competition_label(competitors_data: dict | None) -> str:
    """Coarse Low/Medium/High read on the competitive landscape, from the
    same competitor count competitor_agent.py already extracts - no new
    signal, just a bucketed label for the comparison matrix's Competition
    column. Zero named competitors reads as "Unclear" rather than "Low":
    the same ambiguity viability_score.py's competitionClarity captures
    (could be a real gap, could just be thin search coverage).
    """
    competitors = ((competitors_data or {}).get("competitors")) or []
    count = len(competitors)
    if count == 0:
        return "Unclear"
    if count <= 2:
        return "Low"
    if count <= 4:
        return "Medium"
    return "High"


def _recommendation(score, top_risk: str | None) -> str:
    """A short, deterministic verdict for the comparison matrix -
    templated from the score tier plus the top flagged risk, not a new LLM
    call: this is cosmetic framing over data already computed, the same
    reasoning agent/action_plan.py and agent/experiment_generator.py both
    document for why they're template-based rather than model calls.
    """
    risk_clause = f" Address: {top_risk.lower()}." if top_risk else ""
    if not isinstance(score, (int, float)) or score <= 0:
        return "Not enough signal yet - re-run for a complete analysis."
    if score >= 70:
        return f"Strong candidate - pursue now.{risk_clause}"
    if score >= 45:
        return f"Moderate - needs sharper positioning.{risk_clause}"
    return f"Weak signal - consider pivoting.{risk_clause}"


def _next_steps(action_plan: dict | None) -> list[str]:
    """Flattens agent/action_plan.py's {"next7Days","next30Days","next90Days"}
    windows into one ordered bullet list for Validation History's
    "Suggested next steps" - nearest-term items first, same priority order
    the action plan itself already encodes via window ordering.
    """
    if not isinstance(action_plan, dict):
        return []
    steps = []
    for window in ("next7Days", "next30Days", "next90Days"):
        block = action_plan.get(window)
        if isinstance(block, dict):
            for item in block.get("items") or []:
                text = item.get("text") if isinstance(item, dict) else item
                if text:
                    steps.append(text)
    return steps


def _swot_theme_cloud(contexts: list[dict]) -> dict:
    """Frequency of exact-normalized (lowercased/stripped) recurring
    strengths/risks text across a user's ideas - not fuzzy clustering, so
    two differently-worded but similar points won't merge into one tag.
    With few ideas in a user's history this will look sparse, honestly,
    rather than pretending to find patterns that aren't there yet.
    """
    strengths: Counter = Counter()
    risks: Counter = Counter()
    for context in contexts:
        swot = context.get("swot") or {}
        for item in swot.get("strengths") or []:
            text = item.get("text") if isinstance(item, dict) else item
            if text:
                strengths[text.strip()] += 1
        for item in swot.get("risks") or []:
            text = item.get("risk") if isinstance(item, dict) else item
            if text:
                risks[text.strip()] += 1
    return {
        "strengths": [{"text": text, "count": count} for text, count in strengths.most_common(8)],
        "risks": [{"text": text, "count": count} for text, count in risks.most_common(8)],
    }


def get_user_analytics(user_id: str) -> dict:
    entries = list_sessions_for_user(user_id, limit=100)
    # Paired (entry, session) before filtering - a session can expire/be
    # pruned between list_sessions_for_user's query and this get_session
    # call for it, and dropping the None result from `sessions` without
    # dropping its matching `entry` would silently misalign every
    # subsequent pair in a naive zip(entries, contexts).
    paired = [(entry, get_session(entry["sessionId"])) for entry in entries]
    contexts = [session["context"] for _, session in paired if session]

    scores = []
    high_risk_assumptions = 0
    complete_runs = 0
    confidence_percentages = []
    score_trend = []
    ideas_table = []

    for entry, session in paired:
        if session is None:
            continue
        context = session["context"]

        market = context.get("marketOpportunity") or {}
        score = market.get("opportunityScore")
        has_real_score = isinstance(score, (int, float)) and score > 0
        if has_real_score:
            scores.append({"idea": entry["idea"], "score": score})

        assumptions = ((context.get("assumptions") or {}).get("assumptions")) or []
        high_risk_assumptions += sum(1 for a in assumptions if isinstance(a, dict) and a.get("uncertainty") == "high")

        errors = context.get("errors") or {}
        is_complete = not any(errors.values())
        if is_complete:
            complete_runs += 1

        confidence = context.get("confidence") or {}
        confidence_pct = confidence.get("percentage")
        if isinstance(confidence_pct, (int, float)):
            confidence_percentages.append(confidence_pct)

        risks = [r for r in (context.get("swot") or {}).get("risks") or [] if isinstance(r, dict) and r.get("risk")]
        top_risk = risks[0]["risk"] if risks else None

        if has_real_score:
            score_trend.append(
                {"idea": entry["idea"], "createdAt": entry["createdAt"], "score": score, "confidencePercentage": confidence_pct}
            )

        ideas_table.append(
            {
                "sessionId": entry["sessionId"],
                "idea": entry["idea"],
                "targetCustomer": context.get("targetCustomer"),
                "problem": context.get("problem"),
                "createdAt": entry["createdAt"],
                "score": score if isinstance(score, (int, float)) else None,
                "marketSize": market.get("marketSize"),
                "topRisk": top_risk,
                "risks": risks,
                "assumptions": assumptions,
                "revenueModels": ((context.get("revenueModels") or {}).get("models")) or [],
                "nextSteps": _next_steps(context.get("actionPlan")),
                "competitionLabel": _competition_label(context.get("competitors")),
                "confidencePercentage": confidence_pct,
                "recommendation": _recommendation(score, top_risk),
                "status": "Complete" if is_complete else "Degraded",
            }
        )

    best = max(scores, key=lambda s: s["score"], default=None)

    return {
        "ideasValidated": len(contexts),
        "kpis": {
            "ideasValidated": len(contexts),
            "avgOpportunityScore": round(sum(s["score"] for s in scores) / len(scores)) if scores else None,
            "bestScore": best["score"] if best else None,
            "bestScoreIdea": best["idea"] if best else None,
            "highRiskAssumptions": high_risk_assumptions,
            "completeRuns": complete_runs,
            "degradedRuns": len(contexts) - complete_runs,
            "avgSourceAgreement": round(sum(confidence_percentages) / len(confidence_percentages)) if confidence_percentages else None,
        },
        # Oldest first - a trend line reads left-to-right forward in time,
        # while list_sessions_for_user (and so `ideas` below) orders
        # newest-first for a history list's usual "most recent on top."
        "scoreTrend": sorted(score_trend, key=lambda s: s["createdAt"]),
        "scoreByIdea": [{"idea": s["idea"], "score": s["score"]} for s in scores],
        "assumptionRiskByCategory": _assumption_risk_by_category(contexts),
        "viabilityDimensions": _viability_dimensions(contexts),
        "revenueModelDistribution": _revenue_model_distribution(contexts),
        "swotThemes": _swot_theme_cloud(contexts),
        "ideas": sorted(ideas_table, key=lambda row: row["createdAt"], reverse=True),
    }


__all__ = ["get_user_analytics"]
