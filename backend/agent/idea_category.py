"""Deterministic, keyword-based idea categorization for GET
/admin/platform-metrics' "Top Idea Categories" chart.

No LLM call, by the same reasoning competitor_agent.py uses local NER
instead of a model call: bucketing a pitch into a coarse sector is a
"read obvious keywords off a page" problem, not one that needs open-ended
reasoning, and it would otherwise be a purely cosmetic chart competing for
the same shared Groq quota every other node is trying to protect.

This is intentionally coarse - a rough sector split for an admin chart,
not a claim anyone downstream should treat as authoritative.
"""

_CATEGORY_KEYWORDS = {
    "Fintech": ("bank", "invoic", "payment", "lending", "loan", "fintech", "insurance", "budget", "expense", "crypto", "wallet"),
    "Consumer Health": ("health", "wellness", "fitness", "therapy", "mental", "medical", "clinic", "diet", "sleep", "workout"),
    "Food & Meal Prep": ("meal", "recipe", "grocery", "restaurant", "food", "kitchen", "diet", "nutrition", "cooking"),
    "Sustainability": ("eco", "sustainab", "carbon", "recycl", "green", "renewable", "climate", "compost"),
    "EdTech": ("learn", "course", "student", "teacher", "tutor", "school", "education", "classroom", "curriculum"),
    "Hardware": ("device", "hardware", "sensor", "wearable", "iot", "bluetooth", "gadget", "3d print"),
    "Marketplace": ("marketplace", "platform connecting", "two-sided", "buyers and sellers", "peer-to-peer"),
    "SaaS / B2B Tools": ("saas", "b2b", "workflow", "dashboard", "api", "enterprise", "automation", "productivity", "crm", "analytics platform"),
}

_DEFAULT_CATEGORY = "Other"

# Checked in this order so a pitch matching multiple buckets (e.g. "a meal
# app with a subscription SaaS model") lands on its more specific,
# earlier-listed category rather than the broader "SaaS / B2B Tools"
# catch-all many pitches could technically also match.
_CATEGORY_ORDER = (
    "Fintech",
    "Consumer Health",
    "Food & Meal Prep",
    "Sustainability",
    "EdTech",
    "Hardware",
    "Marketplace",
    "SaaS / B2B Tools",
)


def categorize_idea(idea: str) -> str:
    text = (idea or "").lower()
    for category in _CATEGORY_ORDER:
        if any(keyword in text for keyword in _CATEGORY_KEYWORDS[category]):
            return category
    return _DEFAULT_CATEGORY


__all__ = ["categorize_idea"]
