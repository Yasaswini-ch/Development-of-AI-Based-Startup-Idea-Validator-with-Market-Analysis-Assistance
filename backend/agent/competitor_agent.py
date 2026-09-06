"""
Competitor Discovery & Comparison Agent (Milestone 2).

Identifies real competitors from the Web Search step's results and maps
them out - grounded in that real data, not invented.

Output shape matches the team contract in docs/milestone2-plan.md:

    {
      "competitors": [
        {
          "name": str,
          "offering": str,           # one-line description
          "url": str,
          "gap": str,                # what this idea could do differently/better
          "estimatedPrice": "low" | "mid" | "high" | "unknown",
          "featureBreadth": "narrow" | "moderate" | "broad" | "unknown",
        }
      ]
    }

Uses local Named Entity Recognition (spaCy) to identify competitor names
directly from the already-fetched search results, instead of an LLM call -
by explicit decision, not as a fallback: every LLM call on the shared Groq
key is a call the Market Opportunity agent might need instead, and this
task (recognizing which capitalized phrases in real search snippets are
company names) doesn't need the kind of open-ended reasoning an LLM adds -
it needs to reliably read names off a page, which NER already does well and
for zero API cost, zero rate limit, and zero latency variance.

The real cost of this trade: `gap` can't be a genuine comparative judgment
the way an LLM's would be (that specific field does need reasoning over the
startup idea, which NER can't do), so it's an honest, generic disclosure
instead - see _GAP_DISCLOSURE. `estimatedPrice`/`featureBreadth` are always
"unknown" for the same reason; the frontend already hides badges for
"unknown" values and hides the positioning grid when nothing is
classified, so this degrades cleanly rather than showing fabricated
categories.

Verified against several real ideas (meal-prep delivery, freelance
invoicing, coffee subscriptions, student budgeting): consistently
surfaced the actual real competitors (HelloFresh, Blue Apron, Bluevine,
Rocket Money, MistoBox, Trade Coffee...) that were also independently
confirmed present in the raw search snippets, with a mention-count +
pattern filter cutting out the single-common-word false positives
spaCy's small model is prone to ("Bank", "Unlimited", "Sync" tested and
confirmed filtered).

Comparison-table/listicle sources (a "best budgeting apps" roundup page)
scrape into snippets with one fact per line rather than prose. Naively
squashing those embedded newlines into spaces let NER merge adjacent,
unrelated lines into one garbled multi-word entity ("PocketGuard
Managing Subscriptions") and lose the real competitors that were present
but buried in that noise - confirmed live on a student-budgeting-app
search that returned zero real competitors before this fix, despite
several (Bluevine, Rocket Money) being present in the raw data.
_normalize_snippet_text gives each line its own sentence boundary
instead, which stopped the cross-line bleeding without needing to
discard the whole source.
"""

import logging
import re

logger = logging.getLogger(__name__)

_MAX_COMPETITORS = 4

_GAP_DISCLOSURE = (
    "Identified automatically from search results - a detailed, idea-specific "
    "comparison wasn't generated for this request."
)

# Category/listicle and generic-noun words that spaCy's NER sometimes tags
# as ORG but aren't brand names - either as a full phrase ("Best Meal
# Delivery Services") or standalone ("Bank", "Unlimited", both confirmed
# false positives from real runs). en_core_web_sm (the small model) ships
# without real word-frequency data, so a "how common is this word" check
# isn't reliably available - this denylist is the pragmatic alternative:
# small and extensible as new false positives turn up, rather than a
# heuristic that quietly does nothing on the model we actually have.
_GENERIC_WORDS = {
    "best", "top", "services", "service", "delivery", "meal", "meals",
    "kit", "kits", "guide", "review", "reviews", "app", "apps", "software",
    "market", "industry", "report", "analysis", "options", "bank", "cloud",
    "sync", "unlimited", "premium", "team", "cash", "trade", "exploration",
    "ratings", "rating", "awards", "award",
}

_INTERNAL_CAP = re.compile(r"[a-z][A-Z]")  # e.g. "HelloFresh", "QuickBooks"
_CAMEL_SPLIT = re.compile(r"[A-Z][a-z]*")
_MIN_MENTIONS_WITHOUT_CAMEL_CASE = 2

try:
    import spacy

    _nlp = spacy.load("en_core_web_sm")
except Exception:
    # Missing dependency or model (e.g. a dev environment that hasn't run
    # `python -m spacy download en_core_web_sm`) - degrade to "no competitors
    # identified" rather than crash the whole backend on import.
    logger.warning("spaCy/en_core_web_sm not available - competitor identification disabled", exc_info=True)
    _nlp = None


def _clean_entity_name(name: str) -> str:
    """Collapse whitespace/newlines that sometimes bleed into an entity
    span from the raw snippet text (e.g. "Blue Apron\\n\\nFounded")."""
    return " ".join(name.split())


def _is_generic_phrase(name: str) -> bool:
    words = [w.strip(",.") for w in name.lower().split()]
    return any(w in _GENERIC_WORDS for w in words)


def _is_duplicated_merge(name: str) -> bool:
    """Catch "CostCost"-style artifacts: a scraped comparison table's
    repeated header/label text gets tokenized by spaCy as a single
    camelCase-looking span whose consecutive capitalized segments are the
    same word repeated (confirmed live on a real budgeting-app search
    result). A genuine two-part brand name like "PocketGuard" or
    "HelloFresh" never repeats its own segment, so this only catches the
    artifact, not real names.
    """
    segments = _CAMEL_SPLIT.findall(name)
    return any(a.lower() == b.lower() for a, b in zip(segments, segments[1:]))


def _normalize_snippet_text(title: str, snippet: str) -> str:
    """Give each line of a scraped snippet its own sentence boundary
    instead of squashing embedded newlines into a single space.

    Comparison-table/listicle pages (e.g. a Forbes "best budgeting apps"
    roundup) scrape into a snippet with one fact per line - a company name
    line immediately followed by an unrelated price/feature-label line.
    Joining those with a plain space let spaCy's NER merge adjacent lines
    into one garbled multi-word span ("PocketGuard Managing
    Subscriptions"). Joining with ". " instead gives the parser a sentence
    boundary between lines, so it stops bleeding one table cell's text into
    the next - confirmed live: this alone recovered real competitors
    (Bluevine, Rocket Money) that were previously lost either to being
    merged into garbage or to the whole source being unreadable.
    """
    lines = [line.strip() for line in snippet.split("\n") if line.strip()]
    body = ". ".join(lines)
    return f"{title}. {body}"


def _extract_entities(results: list) -> dict[str, dict]:
    """One pass over the "Competitors"-angle results, tallying how many
    times each cleaned, filtered entity name is mentioned and remembering
    one source result per name (for its URL/snippet).

    A candidate is kept only if it's camelCase (a strong, count-independent
    signal - a very common SaaS/startup naming pattern: HelloFresh,
    QuickBooks, FreshBooks, HoneyBook) or mentioned 2+ times across the
    Competitors-angle results. Repetition across a "best X" listicle is
    itself a reasonable real-brand signal in place of the word-frequency
    check the small spaCy model can't reliably provide - confirmed live:
    this combination correctly returned zero competitors (rather than 3
    confidently wrong ones - "Pacific Northwest", "Single-Origin
    Exploration") for a coffee-subscription idea whose sources didn't
    actually name any companies more than once.
    """
    mentions: dict[str, dict] = {}
    for r in results:
        if r.get("angle") != "Competitors":
            continue
        text = _normalize_snippet_text(r.get("title", ""), r.get("snippet", ""))
        doc = _nlp(text)
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            name = _clean_entity_name(ent.text)
            words = name.split()
            if len(words) > 3 or len(name) < 3 or _is_generic_phrase(name):
                continue
            if _is_duplicated_merge(name):
                continue
            entry = mentions.setdefault(name, {"count": 0, "source": r})
            entry["count"] += 1

    return {
        name: info
        for name, info in mentions.items()
        if _INTERNAL_CAP.search(name) or info["count"] >= _MIN_MENTIONS_WITHOUT_CAMEL_CASE
    }


def _clean_offering(snippet: str) -> str:
    """Collapse a raw snippet's embedded newlines into a single readable
    line before it reaches the frontend - a comparison-table-scraped
    snippet (see _normalize_snippet_text) renders as garbled multi-line
    text like "Noah Kaufman\\n Noah Kaufman\\n\\nBlack and White
    Roasters\\n\\nCoffee" if shown raw, confirmed live."""
    return " ".join(snippet.split())


def _dedupe_near_matches(mentions: dict[str, dict]) -> list[str]:
    """Keep the most-mentioned spelling of a name and drop near-duplicates
    that are substrings of an already-kept one (e.g. "Blue Apron" vs a
    fragment like "Blue Apron  Founded" from an uncleaned snippet)."""
    names = sorted(mentions.keys(), key=lambda n: (-mentions[n]["count"], len(n)))
    kept: list[str] = []
    for name in names:
        if any(name in k or k in name for k in kept):
            continue
        kept.append(name)
    return kept


def analyze_competitors(idea: str, target_customer: str, problem: str, results: list) -> dict:
    """Identify competitors from `results` via local NER - no LLM call, no
    API dependency, so this never fails due to rate limits or provider
    outages. An empty `competitors: []` is a genuine, valid outcome (the
    sources didn't name any identifiable company), not a failure - matches
    the existing contract exactly, so the frontend's null-vs-empty
    distinction still works unchanged.
    """
    if _nlp is None:
        return {"competitors": []}

    mentions = _extract_entities(results)
    kept_names = _dedupe_near_matches(mentions)

    competitors = []
    for name in kept_names[:_MAX_COMPETITORS]:
        source = mentions[name]["source"]
        offering = _clean_offering((source.get("snippet") or "").strip())
        competitors.append(
            {
                "name": name,
                "offering": offering[:200] if offering else "See source for details.",
                "url": source.get("url", ""),
                "gap": _GAP_DISCLOSURE,
                "estimatedPrice": "unknown",
                "featureBreadth": "unknown",
            }
        )

    return {"competitors": competitors}
