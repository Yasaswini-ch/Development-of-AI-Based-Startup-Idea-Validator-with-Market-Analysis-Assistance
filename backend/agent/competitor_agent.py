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
instead - see _GAP_DISCLOSURE.

`estimatedPrice`/`featureBreadth` were "unknown" unconditionally at first
(the same reasoning-limitation as `gap`), which meant the frontend's
positioning grid never had real data to place - correctly built, never
visible. _estimate_price/_estimate_breadth now do a much narrower,
mechanical job instead of the comparative reasoning `gap` needs: pattern-
match $ amounts and a small set of feature-ish keywords in the text right
around each competitor's own mention (see _local_context - deliberately
scoped to 1-2 sentences, not the whole shared source snippet, since two
different competitors from the same source would otherwise get identical,
wrongly-attributed values). Genuinely rough - a $ sign near a name isn't
verified pricing - so both stay "unknown" whenever no signal is found at
all, rather than guessing a bucket. The frontend still hides badges/grid
cells for "unknown" values, so this only adds real classification where
there's real textual evidence, never fabricates one where there isn't.

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

A second, distinct false-positive class was found via cross-industry
testing (a journaling app, a smart water bottle, a bill-negotiation
app): single plain words spaCy's small model mistags as ORG when
mentioned only in passing - "History", "CBT", "Android", "Reply",
"Newsweek" - not merged garbage, just a real word/acronym/company
correctly spelled but not actually being discussed as a product. Unlike
the newline bug, more denylist entries alone don't scale here (each idea
surfaces new ones). _has_product_context requires a single-word,
non-camelCase candidate to appear near actual product language (price,
subscription, "app", "alternative", etc.) in at least one mention,
in addition to the existing 2+-mentions bar - camelCase and multi-word
names (HelloFresh, Rocket Money, Onyx) never needed this and are
unaffected. Verified across 7 ideas: eliminated every single-word false
positive seen without losing any previously-confirmed real competitor.
"""

import json
import logging
import os
import re
import urllib.request

from .structured_output import extract_json_object

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
    # Platform/tech/UI-chrome words that show up as capitalized ORG mentions
    # in almost any product-related source, regardless of the idea's actual
    # domain - "Available on Android and iOS", "Export as PDF", a forum
    # "Reply" link - confirmed live across multiple unrelated ideas (a
    # journaling app and a bill-negotiation app both produced several of
    # these as false-positive "competitors").
    "ai", "pdf", "android", "ios", "iphone", "windows", "mac", "reply",
    "log", "sign", "comment", "comments", "history",
    # Words that keep showing up as one piece of a multi-word merge
    # artifact from scraped page chrome ("The Daily NewsletterReady",
    # "NextSocial Media Monitoring") - confirmed live. These are broadly
    # generic (news/media/scheduling boilerplate), not idea-specific.
    "daily", "newsletter", "social", "media", "monitoring", "next",
    "broadband", "newsweek",
    # News/media outlet names - almost always the publisher citing/
    # reviewing a product, never themselves a competitor to whatever idea
    # is being validated. Same rationale as "newsweek" above; confirmed
    # live ("TechCrunch" surfaced as a "competitor" for a journaling app).
    "techcrunch", "forbes", "reuters", "bloomberg", "cnn", "bbc",
}

_INTERNAL_CAP = re.compile(r"[a-z][A-Z]")  # e.g. "HelloFresh", "QuickBooks"
_CAMEL_SPLIT = re.compile(r"[A-Z][a-z]*")
_MIN_MENTIONS_WITHOUT_CAMEL_CASE = 2

# Words whose presence in the same sentence as a single-word, non-camelCase
# candidate suggest it's actually being discussed as a product - used to
# require more than just "capitalized + mentioned twice" for the riskiest
# candidate shape (see _extract_entities). Not applied to camelCase or
# multi-word names, which are already reliable on their own.
_PRODUCT_CONTEXT_WORDS = {
    "app", "apps", "product", "service", "platform", "tool", "device",
    "subscription", "plan", "price", "pricing", "feature", "features",
    "alternative", "alternatives", "competitor", "compare", "compares",
    "comparison", "vs", "review", "reviews", "tracker", "software",
    "bottle", "wearable", "download", "free", "premium",
}

# Regex + keyword vocabulary for the price/feature-breadth heuristics (see
# _estimate_price / _estimate_breadth). Deliberately small and generic
# rather than domain-specific, since this runs across arbitrary startup
# ideas - a bigger list would mean tuning it per-domain, which doesn't
# scale any better than the entity-name denylist did.
_PRICE_PATTERN = re.compile(
    r"\$\s?([\d,]+(?:\.\d{1,2})?)"
    r"\s*(?:/\s*|per\s+|a\s+)?"
    r"(mo(?:nth)?|yr|year|annually|monthly|yearly)?",
    re.IGNORECASE,
)
_FREE_PATTERN = re.compile(r"\bfree\b", re.IGNORECASE)

_FEATURE_WORDS = {
    "tracking", "budgeting", "invoicing", "reports", "reporting",
    "analytics", "sync", "integration", "integrations", "automation",
    "automatically", "reminders", "alerts", "dashboard", "contracts",
    "proposals", "scheduling", "payments", "negotiate", "negotiation",
    "cancel", "cancellation", "monitor", "monitoring", "coaching",
    "personalized", "categorization", "notifications", "templates",
    "multi-currency", "portal",
}

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


def _has_product_context(sentence: str) -> bool:
    words = {w.strip(",.!?():;$") for w in sentence.lower().split()}
    return bool(words & _PRODUCT_CONTEXT_WORDS) or "$" in sentence


def _local_context(doc, ent) -> str:
    """The entity's own sentence plus the one right after it.

    Comparison-table-style sources often put a name on one line and its
    price on the very next (now the following sentence, post
    _normalize_snippet_text) - using just ent.sent alone would miss that.
    Bounded to two sentences on purpose: this needs to stay about *this*
    competitor, not drift into a neighboring competitor's own pricing in
    the same shared snippet.
    """
    sents = list(doc.sents)
    try:
        idx = sents.index(ent.sent)
    except ValueError:
        return ent.sent.text
    return " ".join(s.text for s in sents[idx : idx + 2])


def _estimate_price(text: str) -> str | None:
    """A rough price bucket from $ amounts near the mention - "rough"
    because it's pattern-matching, not real pricing data (see
    analyze_competitors' docstring for the honesty tradeoff). Returns
    None (not a fabricated bucket) when no price signal is present at
    all, so the field stays "unknown" rather than guessing.
    """
    _YEARLY = {"yr", "year", "annually", "yearly"}

    monthly_amounts = []
    for amount_str, period in _PRICE_PATTERN.findall(text):
        if not period:
            # A bare "$200" with no "/month"/"a year"/etc nearby is too
            # ambiguous to safely bucket - it's exactly this shape that
            # misattributed an unrelated "average household loses $200 a
            # year" statistic as if it were a monthly price, confirmed
            # live against a real Rocket Money mention. Skip rather than
            # guess a period.
            continue
        try:
            amount = float(amount_str.replace(",", ""))
        except ValueError:
            continue
        if period.lower() in _YEARLY:
            amount /= 12
        monthly_amounts.append(amount)

    if monthly_amounts:
        cheapest = min(monthly_amounts)
    elif _FREE_PATTERN.search(text):
        cheapest = 0.0
    else:
        return None

    if cheapest < 10:
        return "low"
    if cheapest < 25:
        return "mid"
    return "high"


def _estimate_breadth(text: str) -> str | None:
    """A rough feature-breadth bucket from how many distinct
    capability-ish words appear near the mention. Same honesty tradeoff
    as _estimate_price - returns None (stays "unknown") rather than
    calling zero detected keywords "narrow", since that's as likely to
    mean "the snippet just didn't happen to describe features" as it is
    to mean a genuinely narrow product.
    """
    lowered = text.lower()
    found = {w for w in _FEATURE_WORDS if w in lowered}
    if not found:
        return None
    if len(found) <= 2:
        return "narrow"
    if len(found) <= 4:
        return "moderate"
    return "broad"


def _extract_entities(results: list) -> dict[str, dict]:
    """One pass over the "Competitors"-angle results, tallying how many
    times each cleaned, filtered entity name is mentioned and remembering
    one source result per name (for its URL/snippet).

    A candidate is kept if it's camelCase (a strong, count-independent
    signal - a very common SaaS/startup naming pattern: HelloFresh,
    QuickBooks, FreshBooks, HoneyBook), or if it's a multi-word phrase
    mentioned 2+ times, or if it's a single plain word mentioned 2+ times
    *and* at least one mention sits in a sentence with product-ish context
    (see _PRODUCT_CONTEXT_WORDS). That last, stricter rule exists because
    single plain words are where spaCy's small model actually gets it
    wrong in practice - confirmed live across several ideas returning
    "History", "CBT", "Android", "Reply", "Apple", "Verizon" as
    "competitors": real proper nouns or acronyms spaCy tags ORG, but
    mentioned only in passing (a platform note, a forum UI element, an
    unrelated company cited in a different context) rather than actually
    being discussed as a product. Requiring nearby product-context text
    doesn't touch camelCase or multi-word names (HelloFresh, Rocket Money,
    Onyx never needed this to be identified correctly) - only the riskiest
    shape gets the extra bar.
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
            entry = mentions.setdefault(
                name,
                {
                    "count": 0,
                    "source": r,
                    "has_context": False,
                    "price": None,
                    "breadth": None,
                    "local_text": "",
                },
            )
            entry["count"] += 1
            if len(words) == 1 and _has_product_context(ent.sent.text):
                entry["has_context"] = True

            local_text = _local_context(doc, ent)
            # Kept even once price/breadth are both already found - the
            # Gemini refinement pass (_refine_with_gemini) needs the same
            # grounding text the regex heuristics used, not just their
            # derived low/mid/high buckets.
            entry["local_text"] = f"{entry['local_text']} {local_text}".strip()
            if entry["price"] is None:
                entry["price"] = _estimate_price(local_text)
            if entry["breadth"] is None:
                entry["breadth"] = _estimate_breadth(local_text)

    kept = {}
    for name, info in mentions.items():
        if _INTERNAL_CAP.search(name):
            kept[name] = info
            continue
        if info["count"] < _MIN_MENTIONS_WITHOUT_CAMEL_CASE:
            continue
        if len(name.split()) == 1 and not info["has_context"]:
            continue
        kept[name] = info
    return kept


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


_GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
_LEVELS = {"low", "mid", "high", "unknown"}
_BREADTHS = {"narrow", "moderate", "broad", "unknown"}


def _valid_gemini_pricing_shape(data: dict) -> bool:
    """Every key in the response must be one of the competitor names we
    actually asked about, and every value must be exactly {"price",
    "featureBreadth"} using only the same enum values estimatedPrice/
    featureBreadth already accept elsewhere - anything else (an unlisted
    name, an invented price bucket) is a shape violation, not just an
    unwanted answer, so extract_json_object rejects it outright rather
    than passing it through.
    """
    if not isinstance(data, dict):
        return False
    for value in data.values():
        if not isinstance(value, dict):
            return False
        if value.get("price") not in _LEVELS or value.get("featureBreadth") not in _BREADTHS:
            return False
    return True


def _refine_with_gemini(idea: str, entries: list[dict]) -> dict[str, dict]:
    """Ask Gemini to classify price/feature-breadth for competitors the
    regex heuristics (_estimate_price/_estimate_breadth) came up
    "unknown" on, using the exact same local grounding text those
    heuristics used - never the raw idea alone, never the model's own
    general knowledge of the company. A separate API key/quota from the
    Groq key the other four agents share (see llm.py), by design: this
    call never competes with Market/SWOT/MVP/GTM for the shared Groq
    rate limit.

    Returns {} on any failure (no key configured, network error, bad
    shape) - callers must treat this as "no refinement available", not
    raise, so a Gemini outage never breaks competitor discovery, which
    is otherwise a zero-external-dependency step.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not entries:
        return {}

    listing = "\n".join(f'- "{e["name"]}": {e["text"][:400]}' for e in entries)
    prompt = (
        f'Startup idea being validated: "{idea}"\n\n'
        "For each competitor below, classify its pricing and feature breadth "
        "using ONLY the text given for that competitor - never your own general "
        "knowledge of the company, never a guess. If the given text doesn't "
        'state or clearly imply a price/breadth, answer "unknown" for that '
        "field rather than inferring one.\n\n"
        f"Competitors:\n{listing}\n\n"
        'Price buckets: "low" (< $10/mo equivalent), "mid" ($10-25/mo), '
        '"high" (> $25/mo), "unknown".\n'
        'Feature breadth: "narrow", "moderate", "broad", "unknown".\n\n'
        "Respond with one JSON object only, keyed by the exact competitor names "
        'given above: {"CompetitorName": {"price": "low|mid|high|unknown", '
        '"featureBreadth": "narrow|moderate|broad|unknown"}}.'
    )

    request = urllib.request.Request(
        _GEMINI_ENDPOINT_TEMPLATE.format(model=_GEMINI_MODEL, key=api_key),
        data=json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 500,
                    # gemini-3.6-flash "thinks" by default, burning most/all of
                    # maxOutputTokens on internal reasoning before writing any
                    # answer text - confirmed live: with this unset, the JSON
                    # answer was truncated mid-string every time, well within
                    # the same 500-token budget. This is a small, mechanical
                    # classification task with no need for extended reasoning.
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
        ).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            body = json.loads(resp.read())
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        logger.warning("Gemini pricing refinement unavailable, keeping regex-only estimates", exc_info=True)
        return {}

    valid_names = {e["name"] for e in entries}
    data = extract_json_object(
        text, lambda d: _valid_gemini_pricing_shape(d) and set(d.keys()) <= valid_names
    )
    return data or {}


def analyze_competitors(idea: str, target_customer: str, problem: str, results: list) -> dict:
    """Identify competitors from `results` via local NER - no LLM call, no
    API dependency, so this never fails due to rate limits or provider
    outages. An empty `competitors: []` is a genuine, valid outcome (the
    sources didn't name any identifiable company), not a failure - matches
    the existing contract exactly, so the frontend's null-vs-empty
    distinction still works unchanged.

    A Gemini refinement pass (_refine_with_gemini) fills in the
    estimatedPrice/featureBreadth cells the regex heuristics left
    "unknown" - separate API key/quota from Groq, optional (skipped
    entirely without GEMINI_API_KEY), and never overrides a value the
    regex heuristics already found, only fills genuine gaps.
    """
    if _nlp is None:
        return {"competitors": []}

    mentions = _extract_entities(results)
    kept_names = _dedupe_near_matches(mentions)
    names_for_this_run = kept_names[:_MAX_COMPETITORS]

    refinable = [
        {"name": name, "text": mentions[name]["local_text"]}
        for name in names_for_this_run
        if mentions[name]["price"] is None or mentions[name]["breadth"] is None
    ]
    refinements = _refine_with_gemini(idea, refinable) if refinable else {}

    competitors = []
    for name in names_for_this_run:
        info = mentions[name]
        source = info["source"]
        offering = _clean_offering((source.get("snippet") or "").strip())
        refined = refinements.get(name, {})
        price = info["price"] or refined.get("price") or "unknown"
        breadth = info["breadth"] or refined.get("featureBreadth") or "unknown"
        competitors.append(
            {
                "name": name,
                "offering": offering[:200] if offering else "See source for details.",
                "url": source.get("url", ""),
                "gap": _GAP_DISCLOSURE,
                "estimatedPrice": price,
                "featureBreadth": breadth,
            }
        )

    return {"competitors": competitors}
