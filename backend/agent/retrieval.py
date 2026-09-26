# agent/retrieval.py

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

DEFAULT_MAX_RESULTS = 5
DEFAULT_SEARCH_RESULTS_PER_QUERY = 8

GENERIC_DOMAINS = {
    "wikipedia.org",
    "dictionary.cambridge.org",
    "merriam-webster.com",
    "britannica.com",
    "geeksforgeeks.org",
    "mbaskool.com",
    "quora.com",
}

GENERIC_TITLE_PATTERNS = (
    "definition",
    "meaning",
    "what is",
    "what are",
    "dictionary",
    "wikipedia",
    "tutorial",
    "example",
    "examples",
    "how to",
)


# ============================================================
# Basic text helpers
# ============================================================

def _clean_text(value: Any) -> str:
    """Clean text safely."""

    if value is None:
        return ""

    text = str(value)

    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def _remove_leading_generic(text: str) -> str:
    """
    Remove generic introductory wording from an idea.
    """

    text = _clean_text(text)

    patterns = [
        r"^ai[- ]powered\s+",
        r"^artificial intelligence[- ]powered\s+",
        r"^an?\s+ai[- ]powered\s+",
        r"^an?\s+artificial intelligence[- ]powered\s+",
        r"^platform\s+that\s+",
        r"^platform\s+for\s+",
        r"^solution\s+that\s+",
        r"^tool\s+that\s+",
        r"^system\s+that\s+",
    ]

    result = text

    for pattern in patterns:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    return result.strip()


# ============================================================
# Academic / domain helpers
# ============================================================

def _is_academic(url: str) -> bool:
    """Return True if URL appears to be from an academic/research source."""

    url = _clean_text(url).lower()

    academic_domains = (
        ".edu",
        ".ac.",
        "arxiv.org",
        "sciencedirect.com",
        "springer.com",
        "nature.com",
        "wiley.com",
        "onlinelibrary.wiley.com",
        "tandfonline.com",
        "researchgate.net",
        "jstor.org",
        "ieeexplore.ieee.org",
        "pubmed.ncbi.nlm.nih.gov",
    )

    return any(domain in url for domain in academic_domains)


def _extract_domain(url: str) -> str:
    """Extract hostname from URL."""

    try:
        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


# ============================================================
# Compact subject
# ============================================================

def _compact_subject(
    idea: str,
    industry: str = "",
    max_words: int = 8,
) -> str:
    """
    Convert a long startup idea into a short search subject.

    IMPORTANT:
    deterministic_fallback.py calls this function with max_words,
    so max_words must remain supported.
    """

    text = _remove_leading_generic(idea).lower()
    industry_text = _clean_text(industry).lower()

    mappings = [
        (
            [
                "customer review",
                "customer reviews",
                "online reviews",
                "review analysis",
                "review analytics",
            ],
            "customer review analytics",
        ),
        (
            [
                "customer feedback",
                "feedback analytics",
                "feedback analysis",
            ],
            "customer feedback analytics",
        ),
        (
            [
                "sentiment analysis",
                "customer sentiment",
            ],
            "customer sentiment analysis",
        ),
        (
            [
                "competitor analysis",
                "competitive analysis",
                "competitor intelligence",
            ],
            "competitive intelligence",
        ),
        (
            [
                "market research",
                "market analysis",
            ],
            "market research",
        ),
        (
            [
                "business intelligence",
                "business analytics",
            ],
            "business intelligence",
        ),
    ]

    # First check the startup idea.
    for patterns, label in mappings:
        if any(pattern in text for pattern in patterns):
            return label

    # Then check industry.
    for patterns, label in mappings:
        if any(pattern in industry_text for pattern in patterns):
            return label

    # Generic fallback.
    stop_words = {
        "an",
        "a",
        "the",
        "and",
        "or",
        "for",
        "to",
        "of",
        "that",
        "with",
        "in",
        "on",
        "is",
        "are",
        "this",
        "platform",
        "system",
        "tool",
        "solution",
        "based",
        "using",
        "used",
        "which",
        "can",
        "helps",
        "help",
        "provides",
        "provide",
    }

    words = [
        word
        for word in text.split()
        if word not in stop_words
    ]

    try:
        limit = max(1, int(max_words))
    except (TypeError, ValueError):
        limit = 8

    result = " ".join(words[:limit])

    return result or "startup idea"


# ============================================================
# Key phrase
# ============================================================

def _key_phrase(
    idea: str,
    industry: str = "",
) -> str:
    """
    Return the primary searchable phrase.
    """

    subject = _compact_subject(
        idea,
        industry=industry,
        max_words=8,
    )

    return subject


# ============================================================
# Distinctive nouns
# ============================================================

def _distinctive_nouns(
    idea: str,
    industry: str = "",
) -> List[str]:
    """
    Extract useful keywords from the startup idea.
    """

    text = _clean_text(
        f"{idea} {industry}"
    ).lower()

    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "to",
        "of",
        "in",
        "on",
        "with",
        "that",
        "this",
        "is",
        "are",
        "be",
        "by",
        "from",
        "as",
        "at",
        "into",
        "through",
        "using",
        "use",
        "based",
        "platform",
        "system",
        "tool",
        "solution",
        "business",
        "businesses",
        "small",
        "medium",
        "sized",
        "size",
        "ai",
        "powered",
        "artificial",
        "intelligence",
    }

    words = re.findall(
        r"[a-zA-Z][a-zA-Z0-9\-]{2,}",
        text,
    )

    result: List[str] = []

    for word in words:

        if word in stop_words:
            continue

        if word not in result:
            result.append(word)

    return result[:12]


# ============================================================
# Search angles
# ============================================================

def build_search_angles(
    idea: str,
    target_customer: str = "",
    problem: str = "",
    industry: str = "",
    location: str = "",
) -> List[Tuple[str, List[str]]]:
    """
    Build multiple search queries around the startup idea.

    Queries intentionally target:
    - market
    - competitors
    - customer pain
    - startups
    - software
    - trends
    """

    idea_clean = _clean_text(idea)
    customer_clean = _clean_text(target_customer)
    problem_clean = _clean_text(problem)
    industry_clean = _clean_text(industry)
    location_clean = _clean_text(location)

    subject = _compact_subject(
        idea_clean,
        industry=industry_clean,
        max_words=8,
    )

    key_phrase = _key_phrase(
        idea_clean,
        industry=industry_clean,
    )

    location_suffix = ""

    if location_clean:
        location_suffix = f" {location_clean}"

    queries: List[str] = []

    # ========================================================
    # Specific domain queries
    # ========================================================

    if "customer review" in subject:
        queries.extend(
            [
                f'"customer feedback analytics" market{location_suffix}',
                f'"customer review analytics" market{location_suffix}',
                f'"review analytics" market{location_suffix}',
                f'"customer feedback analytics" software competitors',
                f'"customer review analytics" companies',
                f'"review management" software alternatives',
                f'"customer feedback analytics" startups funding',
                f'"sentiment analysis" customer reviews startups',
                f'"small business" customer reviews analytics',
                f'"SMB" customer feedback management pain points',
                f'"customer reviews" analytics software businesses',
                f'"online review analytics" software market',
            ]
        )

    elif "customer feedback" in subject:
        queries.extend(
            [
                f'"customer feedback analytics" market{location_suffix}',
                f'"customer feedback management" software competitors',
                f'"customer feedback analytics" startups',
                f'"customer feedback" SMB pain points',
                f'"customer feedback software" market',
                f'"customer feedback analysis" companies',
                f'"customer feedback platform" competitors',
            ]
        )

    elif "competitive intelligence" in subject:
        queries.extend(
            [
                f'"competitive intelligence" software market{location_suffix}',
                f'"competitor analysis software" companies',
                f'"competitive intelligence" startups funding',
                f'"competitor intelligence" SMB',
                f'"competitive analysis tools" market',
            ]
        )

    else:
        queries.extend(
            [
                f'"{key_phrase}" market{location_suffix}',
                f'"{key_phrase}" software competitors',
                f'"{key_phrase}" startups',
                f'"{key_phrase}" market size',
                f'"{key_phrase}" customer pain points',
                f'"{key_phrase}" companies',
            ]
        )

    # ========================================================
    # Customer-specific query
    # ========================================================

    if customer_clean:
        customer_short = " ".join(
            customer_clean.split()[:8]
        )

        queries.append(
            f'"{key_phrase}" "{customer_short}"'
        )

    # ========================================================
    # Problem-specific query
    # ========================================================

    if problem_clean:
        problem_words = problem_clean.split()

        if len(problem_words) > 10:
            problem_short = " ".join(problem_words[:10])
        else:
            problem_short = problem_clean

        queries.append(
            f'"{key_phrase}" "{problem_short}"'
        )

    # ========================================================
    # Industry-specific
    # ========================================================

    if industry_clean:
        industry_short = " ".join(
            industry_clean.split()[:8]
        )

        queries.append(
            f'"{key_phrase}" "{industry_short}"'
        )

    # ========================================================
    # Generic market / startup queries
    # ========================================================

    queries.extend(
        [
            f'"{key_phrase}" market trends',
            f'"{key_phrase}" industry trends',
            f'"{key_phrase}" SaaS',
            f'"{key_phrase}" B2B SaaS',
        ]
    )

    normalized_queries = [
        _clean_text(query).replace('"', "")
        for query in queries
    ]

    return [
        ("Market size & trends", _dedupe_queries(normalized_queries)),
    ]


# ============================================================
# Query deduplication
# ============================================================

def _dedupe_queries(
    queries: Iterable[str],
) -> List[str]:

    seen = set()
    result = []

    for query in queries:

        query = _clean_text(query)

        if not query:
            continue

        key = query.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(query)

    return result


# ============================================================
# Normalize search result
# ============================================================

def _normalize_result(
    result: Any,
) -> Optional[Dict[str, Any]]:
    """
    Normalize results from different search providers.

    DDGS 9.x commonly returns:
        href
        title
        body

    Older versions / other providers may return:
        url
        title
        snippet
    """

    if not isinstance(result, dict):
        return None

    title = (
        result.get("title")
        or result.get("name")
        or ""
    )

    # IMPORTANT:
    # DDGS uses href, not url.
    url = (
        result.get("url")
        or result.get("href")
        or result.get("link")
        or ""
    )

    # IMPORTANT:
    # DDGS uses body, not snippet.
    snippet = (
        result.get("snippet")
        or result.get("body")
        or result.get("description")
        or ""
    )

    title = _clean_text(title)
    url = _clean_text(url)
    snippet = _clean_text(snippet)

    if not url:
        return None

    if not url.startswith(("http://", "https://")):
        return None

    return {
        "title": title,
        "url": url,
        "snippet": snippet,
    }


# ============================================================
# Domain filtering
# ============================================================

def _is_generic_domain(url: str) -> bool:
    domain = _extract_domain(url)

    if not domain:
        return True

    for blocked in GENERIC_DOMAINS:

        if domain == blocked:
            return True

        if domain.endswith("." + blocked):
            return True

    return False


def _is_generic_title(title: str) -> bool:
    title_lower = _clean_text(title).lower()

    if not title_lower:
        return False

    for pattern in GENERIC_TITLE_PATTERNS:

        if title_lower.startswith(pattern):
            return True

    return False


# ============================================================
# Tavily search
# ============================================================

def _search_tavily(
    query: str,
    max_results: int = DEFAULT_SEARCH_RESULTS_PER_QUERY,
) -> List[Dict[str, Any]]:

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        return []

    try:

        from tavily import TavilyClient

        client = TavilyClient(
            api_key=api_key
        )

        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
        )

        results = response.get(
            "results",
            [],
        )

        return results or []

    except Exception as exc:

        logger.warning(
            "Tavily search failed for %r: %s",
            query,
            exc,
        )

        return []


# ============================================================
# DuckDuckGo search
# ============================================================

def _search_ddgs(
    query: str,
    max_results: int = DEFAULT_SEARCH_RESULTS_PER_QUERY,
) -> List[Dict[str, Any]]:

    try:

        from ddgs import DDGS

        with DDGS() as ddgs:

            results = list(
                ddgs.text(
                    query,
                    max_results=max_results,
                )
            )

        return results

    except Exception as exc:

        logger.warning(
            "DDGS search failed for %r: %s",
            query,
            exc,
        )

        return []


# ============================================================
# Unified search
# ============================================================

def _search(
    query: str,
    max_results: int = DEFAULT_SEARCH_RESULTS_PER_QUERY,
) -> List[Dict[str, Any]]:

    tavily_results = _search_tavily(
        query,
        max_results=max_results,
    )

    if tavily_results:

        logger.info(
            '[web_search] Tavily query="%s" results=%d',
            query,
            len(tavily_results),
        )

        return tavily_results

    logger.info(
        "TAVILY_API_KEY not configured or Tavily returned no results. "
        "Using DDGS fallback."
    )

    ddgs_results = _search_ddgs(
        query,
        max_results=max_results,
    )

    logger.info(
        '[web_search] DDGS query="%s" results=%d',
        query,
        len(ddgs_results),
    )

    return ddgs_results


# ============================================================
# Relevance scoring
# ============================================================

def _relevance_score(
    result: Dict[str, Any],
    idea: str,
    target_customer: str = "",
    problem: str = "",
    industry: str = "",
    location: str = "",
) -> float:
    """
    Calculate lightweight local relevance score.

    Score is based on keyword overlap between the startup context
    and search result title/snippet/url.
    """

    title = _clean_text(
        result.get("title", "")
    ).lower()

    snippet = _clean_text(
        result.get("snippet", "")
    ).lower()

    url = _clean_text(
        result.get("url", "")
    ).lower()

    searchable = (
        f"{title} {snippet} {url}"
    )

    context = " ".join(
        [
            _clean_text(idea),
            _clean_text(target_customer),
            _clean_text(problem),
            _clean_text(industry),
            _clean_text(location),
        ]
    ).lower()

    score = 0.0

    # ========================================================
    # Strong exact domain phrases
    # ========================================================

    strong_phrases = [
        "customer review analytics",
        "customer feedback analytics",
        "review analytics",
        "feedback analytics",
        "sentiment analysis",
        "customer sentiment",
        "review management",
        "customer feedback",
        "online reviews",
        "competitive intelligence",
        "competitor analysis",
    ]

    for phrase in strong_phrases:

        if phrase in searchable:

            score += 2.0

            if phrase in context:
                score += 1.0

    # ========================================================
    # Important individual keywords
    # ========================================================

    keywords = [
        "customer",
        "review",
        "reviews",
        "feedback",
        "analytics",
        "sentiment",
        "software",
        "saas",
        "competitor",
        "competition",
        "market",
        "startup",
        "business",
        "smb",
        "small business",
        "medium business",
        "india",
    ]

    for keyword in keywords:

        if keyword in searchable:
            score += 0.5

    # ========================================================
    # Context overlap
    # ========================================================

    context_words = set(
        re.findall(
            r"[a-zA-Z][a-zA-Z0-9\-]{3,}",
            context,
        )
    )

    result_words = set(
        re.findall(
            r"[a-zA-Z][a-zA-Z0-9\-]{3,}",
            searchable,
        )
    )

    stop_words = {
        "this",
        "that",
        "with",
        "from",
        "into",
        "your",
        "their",
        "about",
        "which",
        "what",
        "when",
        "where",
        "have",
        "will",
        "been",
        "were",
        "they",
        "them",
        "than",
        "then",
        "more",
        "some",
        "such",
        "using",
    }

    overlap = (
        context_words
        & result_words
        - stop_words
    )

    score += min(
        len(overlap) * 0.25,
        3.0,
    )

    # ========================================================
    # Academic bonus
    # ========================================================

    if _is_academic(url):
        score += 0.5

    # ========================================================
    # Market/company/source signals
    # ========================================================

    source_signals = [
        "market",
        "funding",
        "startup",
        "company",
        "companies",
        "software",
        "competitor",
        "pricing",
        "customers",
        "industry",
        "research",
        "report",
    ]

    for signal in source_signals:

        if signal in searchable:
            score += 0.2

    return round(
        min(score, 10.0),
        2,
    )


# ============================================================
# Filter results
# ============================================================

def _filter_results(
    results: List[Dict[str, Any]],
    idea: str,
    target_customer: str = "",
    problem: str = "",
    industry: str = "",
    location: str = "",
) -> List[Dict[str, Any]]:

    filtered: List[Dict[str, Any]] = []

    seen_urls = set()

    for raw_result in results:

        result = _normalize_result(raw_result)

        if not result:
            continue

        url = result["url"]

        normalized_url = url.rstrip(
            "/"
        ).lower()

        if normalized_url in seen_urls:
            continue

        seen_urls.add(normalized_url)

        # Block generic domains.
        if _is_generic_domain(url):
            logger.debug(
                "Skipping generic domain: %s",
                url,
            )
            continue

        # Block generic dictionary/tutorial results.
        if _is_generic_title(
            result.get("title", "")
        ):
            logger.debug(
                "Skipping generic title: %s",
                result.get("title", ""),
            )
            continue

        score = _relevance_score(
            result,
            idea=idea,
            target_customer=target_customer,
            problem=problem,
            industry=industry,
            location=location,
        )

        result["relevance_score"] = score

        filtered.append(result)

    # Highest relevance first.
    filtered.sort(
        key=lambda item: (
            item.get("relevance_score", 0.0),
            len(item.get("snippet", "")),
        ),
        reverse=True,
    )

    return filtered


# ============================================================
# Main collect function
# ============================================================

def collect(
    idea: str,
    target_customer: str = "",
    problem: str = "",
    industry: str = "",
    location: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
) -> List[Dict[str, Any]]:
    """
    Collect market/competitor sources for a startup idea.
    """

    logger.info(
        "Retrieval subject: %s",
        _compact_subject(
            idea,
            industry=industry,
        ),
    )

    search_angles = build_search_angles(
        idea=idea,
        target_customer=target_customer,
        problem=problem,
        industry=industry,
        location=location,
    )

    query_count = sum(
        len(angle_queries)
        for _, angle_queries in search_angles
    )

    logger.info(
        "Search angles generated: %d",
        query_count,
    )

    all_results: List[Dict[str, Any]] = []

    # Search each angle.
    for angle, queries in search_angles:

        for query in queries:

            logger.info(
                '[web_search] query="%s"',
                query,
            )

            results = _search(
                query,
                max_results=DEFAULT_SEARCH_RESULTS_PER_QUERY,
            )

            logger.info(
                '[web_search] query="%s" raw_results=%d',
                query,
                len(results),
            )

            for result in results:
                if isinstance(result, dict):
                    all_results.append(
                        {
                            **result,
                            "angle": result.get("angle") or angle,
                        }
                    )
                else:
                    all_results.append(result)

            # Avoid excessive web requests.
            if len(all_results) >= max_results * 8:
                break
        if len(all_results) >= max_results * 8:
            break

    filtered = _filter_results(
        all_results,
        idea=idea,
        target_customer=target_customer,
        problem=problem,
        industry=industry,
        location=location,
    )

    # Keep requested number.
    final_results = filtered[:max_results]

    logger.info(
        "Retrieval finished: %d unique sources",
        len(final_results),
    )

    for index, result in enumerate(
        final_results,
        start=1,
    ):

        logger.info(
            "[web_search] RESULT #%d title=%s url=%s score=%s",
            index,
            result.get("title", ""),
            result.get("url", ""),
            result.get("relevance_score", 0.0),
        )

    return final_results


# ============================================================
# Scoped retrieval
# ============================================================

def collect_scoped(
    idea: str,
    target_customer: str = "",
    problem: str = "",
    industry: str = "",
    location: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
    scope: str = "",
) -> List[Dict[str, Any]]:
    """
    Scoped retrieval.

    scope examples:
        market
        competitor
        customer
        trend
    """

    query_text = _clean_text(idea)

    if (
        query_text
        and not _clean_text(target_customer)
        and not _clean_text(problem)
        and not _clean_text(industry)
        and not _clean_text(location)
        and not _clean_text(scope)
    ):
        scoped_results = fetch_results(
            query_text,
            max_results=max_results,
        )
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for result in scoped_results:
            url = _clean_text(result.get("url", "")).rstrip("/").lower()
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append(
                {
                    **result,
                    "angle": result.get("angle") or "Follow-up research",
                }
            )
        return deduped[:max_results]

    base_angles = build_search_angles(
        idea=idea,
        target_customer=target_customer,
        problem=problem,
        industry=industry,
        location=location,
    )

    scope_lower = _clean_text(scope).lower()

    scoped_queries: List[str] = []

    for _, angle_queries in base_angles:

        for query in angle_queries:

            if scope_lower == "market":

                if any(
                    token in query.lower()
                    for token in [
                        "market",
                        "industry",
                        "trend",
                        "saas",
                    ]
                ):
                    scoped_queries.append(query)

            elif scope_lower == "competitor":

                if any(
                    token in query.lower()
                    for token in [
                        "competitor",
                        "companies",
                        "software",
                        "startup",
                    ]
                ):
                    scoped_queries.append(query)

            elif scope_lower == "customer":

                if any(
                    token in query.lower()
                    for token in [
                        "customer",
                        "smb",
                        "business",
                    ]
                ):
                    scoped_queries.append(query)

            elif scope_lower == "trend":

                if any(
                    token in query.lower()
                    for token in [
                        "trend",
                        "market",
                        "industry",
                    ]
                ):
                    scoped_queries.append(query)

            else:
                scoped_queries.append(query)

    scoped_queries = _dedupe_queries(
        scoped_queries
    )

    results: List[Dict[str, Any]] = []

    for query in scoped_queries:

        results.extend(
            _search(
                query,
                max_results=DEFAULT_SEARCH_RESULTS_PER_QUERY,
            )
        )

        if len(results) >= max_results * 6:
            break

    filtered = _filter_results(
        results,
        idea=idea,
        target_customer=target_customer,
        problem=problem,
        industry=industry,
        location=location,
    )

    return filtered[:max_results]


# ============================================================
# Compact sources
# ============================================================

def compact_sources(
    results: List[Dict[str, Any]],
    max_chars: int = 12000,
) -> str:
    """
    Convert retrieval results into compact text for LLM prompts.
    """

    chunks: List[str] = []

    total_chars = 0

    for index, result in enumerate(
        results,
        start=1,
    ):

        title = _clean_text(
            result.get("title", "")
        )

        url = _clean_text(
            result.get("url", "")
        )

        snippet = _clean_text(
            result.get("snippet", "")
        )

        score = result.get(
            "relevance_score",
            0.0,
        )

        chunk = (
            f"Source {index}\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Relevance: {score}\n"
            f"Summary: {snippet}"
        )

        if total_chars + len(chunk) > max_chars:
            break

        chunks.append(chunk)

        total_chars += len(chunk)

    return "\n\n".join(chunks)


# ============================================================
# Debug helper
# ============================================================

def debug_search_angles(
    idea: str,
    target_customer: str = "",
    problem: str = "",
    industry: str = "",
    location: str = "",
) -> List[str]:
    """
    Return generated search queries for debugging.
    """

    search_angles = build_search_angles(
        idea=idea,
        target_customer=target_customer,
        problem=problem,
        industry=industry,
        location=location,
    )

    flat_queries: List[str] = []

    for _, queries in search_angles:
        flat_queries.extend(queries)

    for index, query in enumerate(
        flat_queries,
        start=1,
    ):
        logger.info(
            "SEARCH ANGLE #%d: %s",
            index,
            query,
        )

    return flat_queries


def fetch_results(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> List[Dict[str, Any]]:
    """
    Fetch and normalize results for a direct query.
    """

    raw_results = _search(
        query,
        max_results=max_results,
    )

    deduped: List[Dict[str, Any]] = []
    seen_urls = set()

    for raw_result in raw_results:
        normalized = _normalize_result(raw_result)
        if not normalized:
            continue

        url = normalized["url"].rstrip("/").lower()
        if url in seen_urls:
            continue

        if _is_generic_domain(normalized["url"]):
            continue

        if _is_generic_title(normalized.get("title", "")):
            continue

        seen_urls.add(url)
        normalized["relevance_score"] = (
            raw_result.get("relevance_score", 0.0)
            if isinstance(raw_result, dict)
            else 0.0
        )
        deduped.append(normalized)

    return deduped[:max_results]