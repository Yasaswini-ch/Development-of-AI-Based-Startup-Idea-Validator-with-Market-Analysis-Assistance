"""Aggregation for GET /admin/platform-metrics.

Combines agent/metrics.py's in-process totals (node success/failure
counts - current totals only, reset on restart) with agent/events.py's
durable log (everything that needs a trend or a recent-rows table) and a
couple of direct sessions_table/users_table queries (daily volume, active
users) into the shape the Platform Health dashboard renders.

What this deliberately does NOT report, rather than fabricate a plausible-
looking number: live Groq/Gemini quota remaining. Nothing in this
codebase polls a provider's real rate-limit headers or knows each model's
configured TPM/RPM ceiling, so a "quota burn" bar here would be invented,
not observed - the model-usage split below is real (agent/events.py's
"model_used" events), the remaining-quota bars are not attempted.
"""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select

from . import events, metrics
from .db import get_engine, sessions_table
from .llm import DEFAULT_MODEL, FALLBACK_MODELS

# The pipeline's genuinely LLM-backed nodes - competitor_discovery uses
# local spaCy NER (no LLM call, see competitor_agent.py), and every
# deterministic node (opportunity_score, white_space, viability_score,
# contradiction_detector, experiment_generator, action_plan, confidence
# nodes) never touches an LLM provider either, so none of them belong in
# an "API success rate" that's specifically about provider calls.
_LLM_NODES = ("market_opportunity", "swot", "mvp", "gtm", "assumption_tracker", "revenue_models")

_ALL_TRACKED_NODES = _LLM_NODES + ("web_search", "competitor_discovery", "opportunity_score", "white_space", "viability_score")


def _pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator) * 100, 1) if denominator else 0.0


def _day_key(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


def _node_rate(snapshot: dict, node: str) -> float | None:
    success = snapshot.get(f"node.{node}.success", 0)
    failure = snapshot.get(f"node.{node}.failure", 0)
    total = success + failure
    return _pct(success, total) if total else None


def _daily_series(rows: list[dict], days: int) -> list[dict]:
    """[{"date": "2026-09-01", "count": N}, ...] for every day in the
    window, oldest first, including days with zero events - a chart with
    gaps silently skipped would misread as "no data collected" rather
    than "zero that day."
    """
    counts = Counter(_day_key(row["createdAt"]) for row in rows)
    now = datetime.now(timezone.utc)
    series = []
    for offset in range(days - 1, -1, -1):
        day = (now.timestamp()) - offset * 86400
        key = _day_key(day)
        series.append({"date": key, "count": counts.get(key, 0)})
    return series


def _active_users(since: float) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            select(sessions_table.c.user_id)
            .where(sessions_table.c.user_id.isnot(None))
            .where(sessions_table.c.created_at >= since)
            .distinct()
        ).all()
    return len(rows)


def get_platform_metrics(days: int = 30) -> dict:
    since = events.window_start(days)
    snapshot = metrics.snapshot()

    cache_hits = events.query("cache_hit", since=since)
    cache_misses = events.query("cache_miss", since=since)
    total_runs = len(cache_misses)  # a cache_miss event is one real pipeline invocation
    total_requests = len(cache_hits) + total_runs
    hits_by_day = Counter(_day_key(r["createdAt"]) for r in cache_hits)

    latency_events = events.query("node_latency", since=since)
    model_events = events.query("model_used", since=since)
    category_events = events.query("idea_category", since=since)
    error_events = events.query("pipeline_error", since=since, limit=200)
    email_events = events.query("email_sent", since=since)

    llm_success = sum(snapshot.get(f"node.{n}.success", 0) for n in _LLM_NODES)
    llm_failure = sum(snapshot.get(f"node.{n}.failure", 0) for n in _LLM_NODES)

    needs_deep_analysis = sum(
        1 for e in error_events if (e["detail"] or {}).get("errorType") == "NeedsDeepAnalysisError"
    )

    avg_latency_by_node = {}
    for node in _ALL_TRACKED_NODES:
        samples = [e["detail"]["seconds"] for e in latency_events if e["node"] == node and e.get("detail")]
        if samples:
            avg_latency_by_node[node] = round(sum(samples) / len(samples), 2)

    overall_latency_samples = [e["detail"]["seconds"] for e in latency_events if e.get("detail")]

    model_counts = Counter((e["detail"] or {}).get("model", "unknown") for e in model_events)
    category_counts = Counter((e["detail"] or {}).get("category", "Other") for e in category_events)

    email_outcomes = Counter((e["detail"] or {}).get("outcome") for e in email_events)
    email_sent_total = sum(v for k, v in email_outcomes.items() if k in ("sent",))
    email_attempted = sum(email_outcomes.values())

    error_rows = [
        {
            "timestamp": datetime.fromtimestamp(e["createdAt"], tz=timezone.utc).isoformat(),
            "node": e["node"],
            "errorType": (e["detail"] or {}).get("errorType", "Unknown"),
            "modelChain": " → ".join((DEFAULT_MODEL, *FALLBACK_MODELS)),
            "outcome": "Deep analysis fallback" if (e["detail"] or {}).get("errorType") == "NeedsDeepAnalysisError" else "Section unavailable",
        }
        for e in error_events[:50]
    ]

    return {
        "windowDays": days,
        "kpis": {
            "totalValidations": total_runs,
            "cacheHitRate": _pct(len(cache_hits), total_requests),
            "apiSuccessRate": _pct(llm_success, llm_success + llm_failure),
            "deepAnalysisRate": _pct(needs_deep_analysis, total_runs),
            "avgLatencySeconds": round(sum(overall_latency_samples) / len(overall_latency_samples), 2) if overall_latency_samples else None,
            "activeUsersThisWeek": _active_users(events.window_start(7)),
        },
        "dailyVolume": _daily_series(cache_misses, days),
        "cacheEfficiency": [
            {**day, "hits": hits_by_day.get(day["date"], 0), "hitRate": _pct(hits_by_day.get(day["date"], 0), hits_by_day.get(day["date"], 0) + day["count"])}
            for day in _daily_series(cache_misses, days)
        ],
        "nodeSuccessRates": {node: _node_rate(snapshot, node) for node in _ALL_TRACKED_NODES if _node_rate(snapshot, node) is not None},
        "modelUsage": [{"model": model, "count": count, "percentage": _pct(count, len(model_events))} for model, count in model_counts.most_common()],
        "latencyByNode": avg_latency_by_node,
        "topCategories": [{"category": cat, "count": count} for cat, count in category_counts.most_common()],
        "recentErrors": error_rows,
        "emailDelivery": {
            "attempted": email_attempted,
            "sent": email_sent_total,
            "deliveryRate": _pct(email_sent_total, email_attempted),
            "failed": email_attempted - email_sent_total,
        },
    }


__all__ = ["get_platform_metrics"]
