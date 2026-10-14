"""Suggests 2-3 revenue models matched to the specific market and customer.

Runs after market_opportunity and competitor_discovery so it can ground
each model in the actual segment and competitive evidence already collected.
No new API calls — input is the already-gathered pipeline artifacts only.
"""

import logging
import re

from crewai import Agent, Crew, Process, Task

from . import events
from .llm import NeedsDeepAnalysisError, get_llm, kickoff_with_fallback, primary_for, AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER
from .prompts.loader import load_prompt
from .structured_output import (
    compact_json,
    compact_sources,
    extract_json_object,
    sanitize_source_ids,
    valid_source_ids,
)

logger = logging.getLogger(__name__)

_FIT_SCORES = {"high", "medium", "low"}
_MAX_MODELS = 3


def _valid_model(item) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item.get("name").strip()
        and item.get("fit") in _FIT_SCORES
        and isinstance(item.get("rationale"), str)
        and item.get("rationale").strip()
        and isinstance(item.get("tradeoffs"), str)
        and item.get("tradeoffs").strip()
        # pricingRange and exampleCompanies are optional for backward compatibility
        and (item.get("pricingRange") is None or isinstance(item.get("pricingRange"), str))
        and (item.get("exampleCompanies") is None or isinstance(item.get("exampleCompanies"), list))
        and valid_source_ids(item.get("sourceIds", []))
    )


def _valid_shape(value: dict) -> bool:
    models = value.get("models")
    if not isinstance(models, list) or not models:
        return False
    return all(_valid_model(item) for item in models)

# Rule-based fallback, used when no language model could answer. It reads how
# the competitors already found describe their own pricing and business model
# and groups those into candidate revenue models. Nothing is invented: a model
# appears only if at least one competitor's text points at it, and every one is
# flagged as inferred from competitor pricing rather than reasoned over.
_MODEL_FAMILIES = (
    ("Subscription", re.compile(r"subscri|per (user|seat|month)|/\s?mo\b|monthly|\bsaas\b|\bseat|\bplans?\b|per year|annual", re.I),
     "Recurring revenue is predictable, but buyers compare it against what rivals already charge and churn if value fades."),
    ("Freemium", re.compile(r"freemium|free (tier|plan|version|trial)|free to (use|start)", re.I),
     "A free tier drives adoption, but only a small share usually upgrades, so it needs a clear paid trigger."),
    ("Usage-based", re.compile(r"usage|pay[- ]as[- ]you[- ]go|per (call|request|transaction|minute|api)|credits?|metered", re.I),
     "Revenue tracks value delivered, but bills are harder to forecast for both sides."),
    ("Commission or transaction fee", re.compile(r"commission|take rate|transaction fee|\d+\s?%\s?(fee|cut)|marketplace fee", re.I),
     "Scales with customer success, but needs enough transaction volume before it covers costs."),
    ("One-time licence", re.compile(r"one[- ]time|lifetime|perpetual|licen[cs]e", re.I),
     "Simple to sell, but revenue stops unless there is a renewal or upgrade path."),
    ("Enterprise or custom pricing", re.compile(r"enterprise|contact sales|custom (pricing|quote)|quote", re.I),
     "Higher deal sizes, but long sales cycles and a heavier sales effort."),
)
_PRICE_TEXT = re.compile(r"[$€£]\s?\d[\d,.]*(?:\s?[-–]\s?[$€£]?\d[\d,.]*)?(?:\s?(?:/|per|a)\s?\w+)?", re.I)


def _fallback_models(competitors: dict | None, valid_ids: set) -> list[dict]:
    rivals = [c for c in (competitors or {}).get("competitors", []) if isinstance(c, dict) and c.get("name")]
    found: dict[str, dict] = {}
    for rival in rivals:
        text = " ".join(str(rival.get(k) or "") for k in ("pricing", "businessModel"))
        if not text.strip().replace("unknown", ""):
            continue
        for name, pattern, tradeoff in _MODEL_FAMILIES:
            if pattern.search(text):
                entry = found.setdefault(name, {"tradeoff": tradeoff, "rivals": [], "prices": [], "ids": []})
                entry["rivals"].append(rival["name"])
                match = _PRICE_TEXT.search(str(rival.get("pricing") or ""))
                if match and match.group(0) not in entry["prices"]:
                    entry["prices"].append(match.group(0).strip())
                ids = rival.get("sourceIds") or ([rival["sourceId"]] if rival.get("sourceId") else [])
                entry["ids"].extend(i for i in ids if i not in entry["ids"])
    ranked = sorted(found.items(), key=lambda kv: -len(kv[1]["rivals"]))[:_MAX_MODELS]
    models = []
    for name, entry in ranked:
        count = len(entry["rivals"])
        models.append(
            {
                "name": name,
                "fit": "high" if count >= 2 else "medium",
                "rationale": (
                    f"{count} of the {len(rivals)} competitors found ({', '.join(entry['rivals'][:3])}) "
                    "describe charging this way, so buyers in this market already expect it. "
                    "Inferred from competitor pricing, not from a model's reasoning."
                ),
                "tradeoffs": entry["tradeoff"],
                "pricingRange": entry["prices"][0] if entry["prices"] else None,
                "exampleCompanies": entry["rivals"][:3],
                "sourceIds": sanitize_source_ids(entry["ids"], valid_ids),
                "inferred": True,
            }
        )
    return models


def _build_crew(
    idea: str,
    target_customer: str,
    context: str,
    model: str,
) -> Crew:
    analyst = Agent(
        role="Monetization Strategist",
        goal="Match revenue models to the specific market dynamics and customer behavior already evidenced.",
        backstory=load_prompt("revenue_system"),
        llm=get_llm(max_tokens=600, model=model),
        max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
        max_iter=AGENT_MAX_ITER,
        verbose=False,
    )
    task = Task(
        description=load_prompt(
            "revenue_task",
            idea=idea,
            target_customer=target_customer or "not specified",
            context=context,
        ),
        expected_output=load_prompt("revenue_output"),
        agent=analyst,
    )
    return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)


def analyze_revenue_models(
    idea: str,
    target_customer: str,
    market_opportunity: dict | None,
    competitors: dict | None,
    results: list,
    allow_local: bool = False,
) -> dict:
    sources = compact_sources(results)
    valid_ids = {source["sourceId"] for source in sources}
    context = compact_json(
        {
            "segments": (market_opportunity or {}).get("segments", [])[:3],
            "competitors": (competitors or {}).get("competitors", [])[:4],
            "sources": sources,
        },
        max_chars=2800,
    )
    try:
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, target_customer, context, model),
            primary=primary_for("revenue"),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            logger.warning("Revenue agent returned no valid JSON")
            raise ValueError("Revenue model analysis did not return a valid result.")
        data["models"] = [
            {
                **item,
                "pricingRange": (item.get("pricingRange") or "").strip() or None,
                "exampleCompanies": [
                    c.strip() for c in (item.get("exampleCompanies") or [])[:3]
                    if isinstance(c, str) and c.strip()
                ],
                "sourceIds": sanitize_source_ids(item.get("sourceIds"), valid_ids),
            }
            for item in data["models"][:_MAX_MODELS]
        ]
        return data
    except Exception as exc:
        # Competitor pricing is already in hand, so a missing model answer
        # should not blank the section (or send the founder to an email
        # prompt just for this one). Only fall through to the old behaviour
        # when there is nothing to build a fallback from.
        models = _fallback_models(competitors, valid_ids)
        if models:
            events.record("llm_fallback", node="revenue_models", detail={"errorType": type(exc).__name__})
            logger.warning("Revenue agent: LLM unavailable, using competitor-pricing fallback", exc_info=True)
            return {"models": models, "degraded": True}
        if not allow_local:
            raise NeedsDeepAnalysisError(str(exc)) from exc
        logger.warning(
            "Revenue agent: LLM unavailable and no competitor pricing to infer from, returning empty models",
            exc_info=True,
        )
        return {"models": [], "degraded": True}
