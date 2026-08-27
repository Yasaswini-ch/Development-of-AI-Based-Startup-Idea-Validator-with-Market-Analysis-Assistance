"""
Retrieval layer: expands one idea into several search angles, fetches each
via agent/tools.py, then merges everything into one clean, deduplicated,
score-ranked list.

Kept separate from tools.py (which only knows how to fetch and score results)
so the "how do we get good, diverse coverage of one idea" logic lives in one
place and doesn't care which sources tools.py is calling underneath.
"""

from urllib.parse import urlparse

from .tools import fetch_results

# Academic/research-paper domains excluded per mentor guidance - they read as
# dense literature review material, not the market/competitor signal a
# founder actually needs from this tool.
_EXCLUDED_DOMAINS = {
    "arxiv.org",
    "researchgate.net",
    "ssrn.com",
    "semanticscholar.org",
    "jstor.org",
    "sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "ieee.org",
    "ieeexplore.ieee.org",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "mdpi.com",
    "dl.acm.org",
    "wiley.com",
    "tandfonline.com",
}


def _is_academic(url: str) -> bool:
    host = urlparse(url).hostname or ""
    host = host.removeprefix("www.")
    return host in _EXCLUDED_DOMAINS


def build_search_angles(idea: str, target_customer: str, problem: str) -> list[tuple[str, str]]:
    """Turn one idea into a few distinct research angles instead of a single
    query, so results cover market sizing, competitors, and demand rather
    than whatever one combined query happens to surface.

    Returns (label, query) pairs - label is a short, human-friendly name for
    grouping results in the UI; query is the actual search string sent out.
    """
    angles = [
        ("Market size & trends", f"{idea} market size and growth trends"),
        ("Competitors", f"{idea} competitors and existing alternatives"),
        ("Industry news", f"{idea} industry news and recent developments"),
    ]
    if target_customer:
        angles.append(("Customer demand", f"{idea} demand among {target_customer}"))
    if problem:
        angles.append(("How others solve this", f"how startups solve: {problem}"))
    return angles


def collect(idea: str, target_customer: str, problem: str, per_angle: int = 8) -> list[dict]:
    """Run every angle, drop duplicate URLs (keeping the higher-scoring copy
    if the same source shows up under more than one angle), filter out
    academic/research-paper sources, and return the combined list ranked by
    computed relevance score, best first. Each result keeps an "angle" label
    alongside its "query" for grouping in the UI.
    """
    angles = build_search_angles(idea, target_customer, problem)

    best_by_url: dict[str, dict] = {}
    for label, query in angles:
        for item in fetch_results(query, max_results=per_angle):
            if _is_academic(item["url"]):
                continue
            item["angle"] = label
            existing = best_by_url.get(item["url"])
            if existing is None or item["score"] > existing["score"]:
                best_by_url[item["url"]] = item

    return sorted(best_by_url.values(), key=lambda r: r["score"], reverse=True)
