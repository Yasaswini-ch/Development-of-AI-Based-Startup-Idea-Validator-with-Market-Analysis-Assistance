"""
Retrieval layer: expands one idea into several search angles, fetches each
via agent/tools.py, then merges everything into one clean, deduplicated,
score-ranked list.

Kept separate from tools.py (which only knows how to fetch and score results)
so the "how do we get good, diverse coverage of one idea" logic lives in one
place and doesn't care which sources tools.py is calling underneath.
"""

import re
from urllib.parse import urlparse

from .tools import fetch_results

try:
    # Reuse the same spaCy model/singleton competitor_agent already loads
    # (zero extra load cost in-process) to pull real nouns out of the idea
    # text, rather than a naive word-position heuristic.
    from .competitor_agent import _nlp
except Exception:  # pragma: no cover - matches competitor_agent's own guard
    _nlp = None

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
    # Generic "alternatives to X" / competitor-directory aggregator sites -
    # their whole content model is a cross-category listicle template, not
    # idea-specific reporting, so they superficially keyword-match almost
    # any "X competitors and alternatives" query while contributing zero
    # real signal. Confirmed live: competitors.app's generic "AI
    # Alternatives" page scored as the *second-highest-relevance* result
    # for a bill-negotiation-app query purely on "AI"/"alternatives"/
    # "competitors" keyword overlap, and its scraped listicle content fed
    # unrelated app names into Competitor Discovery's NER step as false
    # "competitors" for that idea.
    "competitors.app",
    "alternativeto.net",
    "saashub.com",
}


def _is_academic(url: str) -> bool:
    host = urlparse(url).hostname or ""
    host = host.removeprefix("www.")
    return host in _EXCLUDED_DOMAINS


# Trailing function words that make a truncated query fragment read as a
# mid-sentence cut ("... aged 25-45 who", "... hard because recipes")
# instead of a clean noun phrase. Stripped iteratively off the *end* only,
# after word-count truncation, since a free-tier search provider matches a
# dangling connector word far worse than the same query one word shorter -
# confirmed live: "...aged 25-45 who" returned 0 results, the same fragment
# with trailing stopwords trimmed returned real matches.
_TRAILING_STOPWORDS = {
    "who",
    "which",
    "that",
    "because",
    "since",
    "is",
    "are",
    "was",
    "were",
    "and",
    "or",
    "but",
    "at",
    "in",
    "on",
    "for",
    "with",
    "of",
    "to",
    "the",
    "a",
    "an",
    "do",
    "does",
    "did",
    "not",
}


def _compact_subject(text: str, max_words: int = 10) -> str:
    """Keep search queries short enough for free providers to match reliably."""
    cleaned = " ".join(text.split()).strip(" .,:;-")
    if not cleaned:
        return ""

    # Product descriptions commonly start with the useful noun phrase and
    # continue with "that/which ...". Search engines perform better when the
    # long feature clause is removed from every angle.
    cleaned = re.split(r"\b(?:that|which)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.sub(
        r"^(?:an?\s+|the\s+)?(?:ai[- ]powered|artificial intelligence[- ]powered|smart|intelligent)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # A leading "a/an/the" is dead weight in a search query regardless of
    # what follows it - strip it unconditionally, not just ahead of an
    # "ai-powered" style adjective.
    cleaned = re.sub(r"^(?:an?|the)\s+", "", cleaned, flags=re.IGNORECASE)
    words = cleaned.split()[:max_words]
    while words and words[-1].lower() in _TRAILING_STOPWORDS:
        words.pop()
    return " ".join(words)


# Filler words dropped from *anywhere* in free-text customer/problem
# fields, not just the end - unlike _compact_subject (which keeps a
# product description's natural word order intact), a user-written
# sentence like "...aged 25-45 who enjoy mixology but do not want to buy
# full bottles..." reads as a garbled, ungrammatical fragment once merely
# truncated to N words, and free search providers (DuckDuckGo/Wikipedia)
# were confirmed live to return zero results for that fragment while
# matching fine on the same content words with filler stripped out.
_FILLER_WORDS = _TRAILING_STOPWORDS | {
    "but",
    "not",
    "do",
    "does",
    "did",
    "want",
    "enjoy",
    "this",
    "these",
    "those",
    "their",
    "they",
    "them",
    "it",
    "its",
}


def _key_phrase(text: str, max_words: int = 5) -> str:
    """Extract the first few *content* words (filler dropped, original
    order preserved) instead of a literal N-word prefix - turns a full
    sentence into a short, keyword-dense search phrase.
    """
    cleaned = " ".join(text.split()).strip(" .,:;-")
    if not cleaned:
        return ""
    words = [w for w in cleaned.split() if w.lower() not in _FILLER_WORDS]
    return " ".join(words[:max_words])


# Generic product/business-type nouns that show up in almost every startup
# pitch regardless of domain ("subscription", "app", "platform"...) and
# therefore match huge numbers of completely unrelated pages (a dictionary
# definition of "subscription", Netflix, HBO) with no real topical overlap.
# Excluded from the *distinctive*-noun pick specifically - they still show
# up in `subject` via _compact_subject, just aren't trusted alone to prove
# a result is relevant.
_GENERIC_PRODUCT_NOUNS = {
    "service", "services", "platform", "platforms", "app", "apps",
    "application", "applications", "tool", "tools", "solution",
    "solutions", "product", "products", "business", "businesses",
    "company", "companies", "subscription", "subscriptions", "box",
    "boxes", "system", "systems", "software", "startup", "idea",
    # "What's inside the box" structural nouns - real, non-generic words,
    # but describe *how* a delivery/kit business is packaged rather than
    # *what domain* it's in, so they show up across totally unrelated
    # subscription businesses (meal kits, craft kits, cocktail kits all
    # ship "ingredients"/"recipes"/"kits"). Confirmed live: ranking
    # "ingredients" above "cocktails"/"bartenders" purely for being a
    # longer word produced a fallback query that matched generic
    # "Meal kit"/"Home Chef" pages instead of anything cocktail-related.
    "ingredients", "ingredient", "recipes", "recipe", "kit", "kits",
    "items", "item", "supplies", "materials", "contents", "plans", "plan",
    "features", "package", "packages", "delivery", "deliveries",
}


def _distinctive_nouns(text: str, max_words: int = 3) -> list[str]:
    """Real nouns from the idea text, ranked by length (a cheap proxy for
    specificity, same trick as tools._keyword_weight) and generic
    product-type nouns excluded, so the actual domain the idea is *about*
    (e.g. "cocktails", "bartenders") isn't lost.

    This exists because the old subject extraction split the idea at the
    first "that/which" and kept only what came *before* it - which for a
    pitch phrased as "A subscription box service that delivers ... for
    home bartenders to make craft cocktails" is exactly the generic
    opening noun phrase, discarding the entire clause holding every real,
    differentiating word. Confirmed live: without this, every
    Market/Competitors/Industry-news query for that idea searched only
    "subscription box service" with zero reference to cocktails at all,
    surfacing Netflix, HBO, and dictionary-definition pages as top
    "matches".
    """
    if _nlp is None:
        return []
    doc = _nlp(text)
    seen: set[str] = set()
    candidates = []
    for token in doc:
        if token.pos_ not in ("NOUN", "PROPN"):
            continue
        word = token.text
        lw = word.lower()
        if lw in _GENERIC_PRODUCT_NOUNS or lw in seen or len(word) <= 2:
            continue
        seen.add(lw)
        candidates.append(word)
    candidates.sort(key=len, reverse=True)
    return candidates[:max_words]


def build_search_angles(idea: str, target_customer: str, problem: str) -> list[tuple[str, list[str]]]:
    """Turn one idea into a few distinct research angles instead of a single
    query, so results cover market sizing, competitors, and demand rather
    than whatever one combined query happens to surface.

    Returns (label, [query, ...fallback queries]) pairs - label is a short,
    human-friendly name for grouping results in the UI. Each angle carries
    more than one candidate query, tried in order by collect(): the free
    DuckDuckGo/Wikipedia search backing this when no Tavily key is set is
    confirmed live to be flaky per exact query wording - the same subject
    can return 0 raw hits with one extra word and several hits with it
    removed, independent of relevance. A shorter, more generic fallback
    gives an angle a second chance instead of surfacing "no reliable
    sources" purely because its first-choice query didn't happen to match
    anything today.
    """
    prefix = _compact_subject(idea, max_words=1)
    distinctive = _distinctive_nouns(idea, max_words=3)
    distinctive_new = [w for w in distinctive if w.lower() not in prefix.lower()]
    subject = " ".join([prefix] + distinctive_new) or prefix
    subject_fallback = " ".join([prefix] + distinctive_new[:1]) if distinctive_new else prefix
    # Shorter than `subject`: DuckDuckGo's free-tier search is an implicit
    # AND across every term, and confirmed live to return zero hits once a
    # query combines the full subject *and* several customer/problem
    # keywords (too many required terms for any one page to satisfy).
    # Trading some specificity for a shorter, more matchable query.
    short_subject = " ".join([prefix] + distinctive[:1]) if distinctive else prefix
    customer = _key_phrase(target_customer, max_words=3)
    problem_subject = _key_phrase(problem, max_words=3)

    angles = [
        ("Market size & trends", [f"{subject} market size", f"{subject_fallback} market"]),
        ("Competitors", [f"{subject} competitors alternatives", f"{subject_fallback} competitors"]),
        ("Industry news", [f"{subject} industry news", f"{subject_fallback} news"]),
    ]
    if customer:
        angles.append(("Customer demand", [f"{short_subject} {customer} demand", f"{prefix} {customer}"]))
    if problem_subject:
        angles.append(
            ("How others solve this", [f"{short_subject} {problem_subject} solutions", f"{prefix} {problem_subject}"])
        )
    return angles


def collect(idea: str, target_customer: str, problem: str, per_angle: int = 10) -> list[dict]:
    """Run every angle, drop duplicate URLs *within the same angle*, filter
    out academic/research-paper sources, and return the combined list ranked
    by computed relevance score, best first. Each result keeps an "angle"
    label alongside its "query" for grouping in the UI.

    Dedup is scoped per angle (not globally across all angles): a genuinely
    relevant source can legitimately answer more than one research
    question - e.g. a "best meal planning apps" roundup is evidence for both
    "Competitors" and "How others solve this". Collapsing it down to a
    single angle (the old behavior) silently emptied out whichever angle
    lost the tie-break, showing "no reliable sources" for a group that
    actually had matching evidence - confirmed live: a real result existed
    but only under a different tab than the one it was evidence for.
    """
    angles = build_search_angles(idea, target_customer, problem)

    best_by_angle_url: dict[tuple[str, str], dict] = {}
    for label, queries in angles:
        for query in queries:
            hits = [item for item in fetch_results(query, max_results=per_angle) if not _is_academic(item["url"])]
            if not hits:
                # Try the next, shorter/more generic candidate query for
                # this angle instead of giving up - see build_search_angles.
                continue
            for item in hits:
                item["angle"] = label
                key = (label, item["url"])
                existing = best_by_angle_url.get(key)
                if existing is None or item["score"] > existing["score"]:
                    best_by_angle_url[key] = item
            break

    return sorted(best_by_angle_url.values(), key=lambda r: r["score"], reverse=True)


def collect_scoped(query: str, max_results: int = 5) -> list[dict]:
    """Run one bounded follow-up query for chat instead of all research angles."""
    query = " ".join(query.split()).strip()
    if not query:
        return []

    best_by_url = {}
    for raw_item in fetch_results(query, max_results=max_results):
        item = dict(raw_item)
        url = item.get("url", "")
        if not url or _is_academic(url):
            continue
        item["angle"] = "Follow-up research"
        item["query"] = query
        existing = best_by_url.get(url)
        if existing is None or item.get("score", 0) > existing.get("score", 0):
            best_by_url[url] = item
    return sorted(best_by_url.values(), key=lambda result: result.get("score", 0), reverse=True)
