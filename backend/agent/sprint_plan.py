"""A 4-week validation sprint and a customer-interview script.

Both are recombined from what the pipeline already produced (the assumption
tracker's how-to-validate steps and risk-if-wrong, the experiment generator's
success metrics) - deterministic, no LLM call, so they cost no quota and can
never invent a figure the report does not already contain.

The sprint orders the work: riskiest assumptions first, then customer
conversations, then a smoke test, then a decision against fixed rules. The
interview script follows the "ask about past behaviour, never pitch" approach:
generic opening questions plus one probe per top assumption, each with what
would confirm it and what would count against it.
"""

import re

_MAX_ASSUMPTION_TASKS = 2
_MAX_SCRIPT_ASSUMPTIONS = 3

# Questions that ask about what the person already does, by assumption category.
_PROBES = {
    "demand": "What do you use today to deal with this, and roughly what does it cost you each month in money or hours?",
    "market": "Who else around you has this problem, and how do they deal with it?",
    "technical": "Which tools have you tried for this before, and what made you stop using them?",
    "competitive": "What did you compare before choosing what you use now, and why did the others lose?",
    "regulatory": "Is there anything about your work or clients that limits which tools you are allowed to use?",
}
_DEFAULT_PROBE = "How do you handle this today, step by step?"


def _days(text) -> float:
    """Rough length of a 'timeToValidate' string, to put the quickest checks first."""
    s = str(text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    n = float(m.group(1)) if m else 99.0
    if "month" in s:
        return n * 30
    if "week" in s:
        return n * 7
    return n


def _clean(text) -> str:
    return " ".join(str(text or "").split()).strip()


def _high_uncertainty(assumptions: dict | None) -> list[dict]:
    items = [a for a in (assumptions or {}).get("assumptions") or [] if isinstance(a, dict) and _clean(a.get("assumption"))]
    ranked = sorted(items, key=lambda a: (a.get("uncertainty") != "high", _days(a.get("timeToValidate"))))
    return ranked


def _distinct_experiments(experiments) -> list[dict]:
    seen, out = set(), []
    for e in experiments or []:
        if not isinstance(e, dict):
            continue
        method = _clean(e.get("method"))
        if method and method not in seen:
            seen.add(method)
            out.append(e)
    return out


def build_sprint(assumptions: dict | None, experiments: list | None) -> dict | None:
    ranked = _high_uncertainty(assumptions)
    if not ranked:
        return None

    week1 = []
    for a in ranked[:_MAX_ASSUMPTION_TASKS]:
        week1.append({
            "task": _clean(a.get("howToValidate")) or f"Find evidence for: {_clean(a.get('assumption'))}",
            "confirmsIf": f"Evidence supports: {_clean(a.get('assumption'))}",
            "killsIf": _clean(a.get("riskIfWrong")) or "The evidence contradicts the assumption.",
        })

    week3 = []
    for e in _distinct_experiments(experiments)[:2]:
        week3.append({
            "task": _clean(e.get("method")),
            "confirmsIf": _clean(e.get("successMetric")) or "The target action rate is met.",
            "killsIf": "The target action rate is clearly missed.",
        })
    for a in ranked[_MAX_ASSUMPTION_TASKS:_MAX_ASSUMPTION_TASKS + 1]:
        week3.append({
            "task": _clean(a.get("howToValidate")) or f"Find evidence for: {_clean(a.get('assumption'))}",
            "confirmsIf": f"Evidence supports: {_clean(a.get('assumption'))}",
            "killsIf": _clean(a.get("riskIfWrong")) or "The evidence contradicts the assumption.",
        })

    return {
        "weeks": [
            {"week": 1, "title": "Test the riskiest assumptions", "tasks": week1},
            {"week": 2, "title": "Talk to customers", "tasks": [{
                "task": "Run 5 to 8 short interviews with people who match the target customer, using the interview script in this report.",
                "confirmsIf": "At least 3 describe the problem unprompted and already spend time or money on it.",
                "killsIf": "Fewer than 2 recognise the problem, or nobody has tried to solve it.",
            }]},
            {"week": 3, "title": "Run a cheap smoke test", "tasks": week3},
            {"week": 4, "title": "Decide", "tasks": [{
                "task": "Compare the results of weeks 1 to 3 with the thresholds above and make the call.",
                "confirmsIf": "Most checks passed and no high-severity risk is left without a mitigation: go on to build the MVP.",
                "killsIf": "Most checks failed: drop the idea, or rework the customer or problem and run a new validation.",
            }]},
        ],
        "note": "Built from this report's own assumptions and experiments; thresholds are the ones those steps state.",
    }


def build_interview_script(idea: str, target_customer: str, problem: str, assumptions: dict | None) -> dict | None:
    ranked = _high_uncertainty(assumptions)
    if not ranked:
        return None
    problem = _clean(problem)
    opening = [
        f"Tell me about the last time this came up for you{': ' + problem if problem else ''}. What happened?",
        "What did you do about it, and how long did that take?",
        "Have you ever paid for something to help with this? What, and how much?",
    ]
    probes = []
    for a in ranked[:_MAX_SCRIPT_ASSUMPTIONS]:
        probes.append({
            "assumption": _clean(a.get("assumption")),
            "ask": _PROBES.get(a.get("category"), _DEFAULT_PROBE),
            "listenFor": _clean(a.get("howToValidate")) or "Concrete past behaviour that supports the assumption.",
            "redFlag": _clean(a.get("riskIfWrong")) or "They describe no real cost or effort today.",
        })
    return {
        "audience": _clean(target_customer),
        "rules": [
            "Ask about what they did in the past, not what they would do in future.",
            "Do not pitch the idea until the end, and do not defend it.",
            "Write down their words; count the people, not the compliments.",
        ],
        "opening": opening,
        "probes": probes,
        "closing": [
            "Who else should I talk to about this?",
            "Can I come back to you when there is something to try?",
        ],
    }
