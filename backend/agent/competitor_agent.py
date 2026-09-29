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
import urllib.parse
import urllib.request

from .structured_output import extract_json_object

# crewai/llm are imported lazily inside _profile_with_llm: every other
# path in this module is deliberately dependency-light (spaCy only), and
# tests that exercise NER alone shouldn't have to import the LLM stack.

logger = logging.getLogger(__name__)

# No product-imposed cap on how many competitors get shown - Yalene asked for
# every genuinely-grounded competitor the evidence supports, not an arbitrary
# top-N. This is still a real ceiling, not "unlimited": each competitor must
# be grounded to a source (_ground_and_clean_competitors), and the
# "Competitors" search angle itself is bounded to ~20 raw results
# (retrieval.py's per_angle=10 x _QUERIES_PER_ANGLE["Competitors"]=2), so in
# practice this can never return more distinct, evidenced names than that -
# raised here mainly so the count is no longer artificially truncated below
# what the evidence actually supports.
_MAX_COMPETITORS = 20

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
    """Collapse a raw snippet into a single readable line.
    Strips markdown headers/bold/italic that some search results return
    as raw markup (e.g. '#### Pros', '## provider'), then collapses
    embedded newlines."""
    import re as _re
    text = _re.sub(r"^#{1,6}\s+", "", snippet, flags=_re.MULTILINE)
    text = _re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = _re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    return " ".join(text.split())


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


_CLASSIFICATIONS = {"direct", "indirect", "unknown"}
_MAX_LIST_ITEMS = 3
_MAX_MATRIX_ROWS = 5


def _short_text(value, limit: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] if cleaned else None


def _short_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_short_text(v, 120) for v in value]
    return [v for v in items if v][:_MAX_LIST_ITEMS]


def _valid_profile_shape(data: dict, names: set[str]) -> bool:
    """Only the top-level shape is strict (a "profiles" object keyed by
    names we actually asked about); individual fields are sanitized by
    _clean_profile instead, so one malformed field drops that field rather
    than the whole profiling pass."""
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        return False
    if not set(profiles.keys()) <= names:
        return False
    return all(isinstance(v, dict) for v in profiles.values())


def _clean_profile(raw: dict) -> dict:
    classification = raw.get("classification")
    return {
        "classification": classification if classification in _CLASSIFICATIONS else "unknown",
        "pricing": _short_text(raw.get("pricing"), 80) or "unknown",
        "businessModel": _short_text(raw.get("businessModel"), 80) or "unknown",
        "strengths": _short_list(raw.get("strengths")),
        "weaknesses": _short_list(raw.get("weaknesses")),
        "gap": _short_text(raw.get("gap"), 240),
    }


def _clean_matrix(raw, names: set[str]) -> list[dict]:
    """Keep only rows with a dimension and an idea cell, and only cells
    for competitors we actually profiled - a model-invented competitor
    name in the matrix is dropped, same rule as sanitize_source_ids."""
    if not isinstance(raw, list):
        return []
    rows = []
    for row in raw[:_MAX_MATRIX_ROWS]:
        if not isinstance(row, dict):
            continue
        dimension = _short_text(row.get("dimension"), 60)
        idea_cell = _short_text(row.get("idea"), 140)
        cells = row.get("competitors")
        if not dimension or not idea_cell or not isinstance(cells, dict):
            continue
        rows.append(
            {
                "dimension": dimension,
                "idea": idea_cell,
                "competitors": {
                    name: _short_text(cells.get(name), 140) or "unknown" for name in names if name in cells
                },
            }
        )
    return rows


_PRICE_LABELS = {
    "low": "Low (under $10/mo)",
    "mid": "Mid ($10-25/mo)",
    "high": "High (over $25/mo)",
    "unknown": "unknown",
}
_BREADTH_LABELS = {
    "narrow": "Narrow - a focused feature set",
    "moderate": "Moderate feature set",
    "broad": "Broad feature set",
    "unknown": "unknown",
}
_CLASSIFICATION_LABELS = {
    "direct": "Direct competitor",
    "indirect": "Indirect competitor",
    "unknown": "Unclear positioning",
}


def _build_fallback_matrix(competitors: list[dict]) -> list[dict]:
    """A deterministic comparisonMatrix built only from fields this module
    already computes for every competitor (estimatedPrice, featureBreadth,
    classification) - used whenever the LLM discovery pass didn't produce
    one (it wasn't run, timed out, or found no competitors to build one
    from), so the comparison view isn't contingent on that one LLM call
    succeeding. It's honest about the idea's own side: at validation time
    there's no real pricing or shipped feature set to compare with, so the
    "idea" column says exactly that instead of inventing one - same
    fabricate-nothing rule the rest of this module follows (see
    _GAP_DISCLOSURE for the same tradeoff on a different field).
    """
    if not competitors:
        return []
    return [
        {
            "dimension": "Price",
            "idea": "Not yet priced - pre-launch",
            "competitors": {c["name"]: _PRICE_LABELS[c.get("estimatedPrice", "unknown")] for c in competitors},
        },
        {
            "dimension": "Feature breadth",
            "idea": "Not yet built - pre-launch",
            "competitors": {c["name"]: _BREADTH_LABELS[c.get("featureBreadth", "unknown")] for c in competitors},
        },
        {
            "dimension": "Positioning",
            "idea": "New entrant addressing this need",
            "competitors": {
                c["name"]: _CLASSIFICATION_LABELS[c.get("classification", "unknown")] for c in competitors
            },
        },
    ]


_MAX_ENRICHED = 4
_WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
_WIKIDATA_FOUNDING_YEAR = re.compile(r"\b(1[89]\d{2}|20[0-4]\d)\b")
_PRODUCTHUNT_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"


def _wikidata_lookup(name: str) -> dict | None:
    """A free, keyless enrichment source for established companies:
    Wikidata's public search + entity APIs. Looks up `name`, and if the
    top hit's own label is a reasonably close match (not a generic
    disambiguation page or an unrelated entity that merely contains the
    word), returns its short description, a rough founding year pulled
    from that description if stated, and a link to the Wikidata item.

    Best-effort like _refine_with_gemini: returns None on any failure
    (network error, no match, unexpected shape), never raises, so a
    Wikidata outage never affects competitor discovery itself.
    """
    try:
        search_url = (
            f"{_WIKIDATA_SEARCH_URL}?action=wbsearchentities&search="
            f"{urllib.parse.quote(name)}&language=en&type=item&limit=1&format=json"
        )
        with urllib.request.urlopen(search_url, timeout=5) as resp:
            hits = json.loads(resp.read()).get("search") or []
        if not hits:
            return None
        hit = hits[0]
        if hit.get("label", "").strip().lower() != name.strip().lower():
            # A loose/partial match is more likely a false hit (a person,
            # an unrelated org sharing a word) than the actual company -
            # skip rather than attach the wrong company's data.
            return None
        description = (hit.get("description") or "").strip()
        year_match = _WIKIDATA_FOUNDING_YEAR.search(description)
        return {
            "source": "wikidata",
            "description": description or None,
            "foundedYear": int(year_match.group(0)) if year_match else None,
            "url": f"https://www.wikidata.org/wiki/{hit['id']}",
        }
    except Exception:
        logger.warning("Wikidata enrichment unavailable for %r", name, exc_info=True)
        return None


def _producthunt_lookup(name: str) -> dict | None:
    """A free (developer-token) enrichment source for software/app
    competitors: Product Hunt's v2 GraphQL API. Requires
    PRODUCTHUNT_API_TOKEN; returns None immediately without one, and on
    any request/shape failure, same best-effort contract as
    _wikidata_lookup - this can never break competitor discovery.

    Searches posts for the competitor's name (`posts(query: $name)`) and
    prefers an exact case-insensitive name match, falling back to the top
    search result when none matches. The variable must be both declared and
    used in the query body - an unused `$name` is invalid GraphQL.
    """
    token = os.environ.get("PRODUCTHUNT_API_TOKEN")
    if not token:
        return None
    # PH v2 GraphQL `posts` supports a `query` argument for full-text search.
    # The previous version fetched the top 3 all-time posts with no filter,
    # then exact-name-matched against that tiny list — almost never a hit.
    # Passing `query: $name` makes PH actually search for the competitor name.
    try:
        request = urllib.request.Request(
            _PRODUCTHUNT_ENDPOINT,
            data=json.dumps(
                {
                    "query": (
                        "query SearchProduct($name: String!) { "
                        "posts(query: $name, first: 5, order: VOTES) { "
                        "edges { node { name tagline votesCount website url } } } }"
                    ),
                    "variables": {"name": name},
                }
            ).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=5) as resp:
            body = json.loads(resp.read())
        edges = body.get("data", {}).get("posts", {}).get("edges") or []
        nodes = [e["node"] for e in edges if e.get("node")]
        # Prefer an exact name match; fall back to the top search result.
        match = next(
            (n for n in nodes if n.get("name", "").lower() == name.lower()),
            nodes[0] if nodes else None,
        )
        if not match:
            return None
        return {
            "source": "producthunt",
            "tagline": match.get("tagline"),
            "votesCount": match.get("votesCount"),
            "website": match.get("website"),
            "url": match.get("url"),
        }
    except Exception:
        logger.warning("Product Hunt enrichment unavailable for %r", name, exc_info=True)
        return None


def _enrich_with_apis(competitors: list[dict]) -> None:
    """Best-effort, additive enrichment of the top _MAX_ENRICHED
    competitors with external company data (Product Hunt for software/app
    products, Wikidata for established companies) - see
    docs/competitor-detection-and-confidence-scoring-proposal.md Option C.
    Mutates each competitor dict in place, adding an "enrichment" key only
    when a source actually matched; never removes or overrides an existing
    field, and never raises - a provider outage or missing token just means
    no enrichment for that run, exactly like the Gemini refinement pass.
    Bounded to the top few competitors (not all _MAX_COMPETITORS) to keep
    external call volume small regardless of how many are found.
    """
    for competitor in competitors[:_MAX_ENRICHED]:
        name = competitor["name"]
        enrichment = _producthunt_lookup(name) or _wikidata_lookup(name)
        if enrichment:
            competitor["enrichment"] = enrichment


def _valid_discovery_shape(data: dict) -> bool:
    """Only the top-level shape is strict; per-competitor fields are
    sanitized (and grounding-checked) by _ground_and_clean_competitors, so
    one malformed competitor drops that competitor rather than the whole
    discovery pass. "competitors": [] is a valid shape (a genuine "no
    competitors in these sources" finding), unlike the old profiling
    pass's non-empty requirement - discovery is allowed to say "none",
    since unlike profiling it isn't just decorating names NER already
    found.
    """
    if not isinstance(data, dict):
        return False
    competitors = data.get("competitors")
    if not isinstance(competitors, list):
        return False
    return all(isinstance(c, dict) and isinstance(c.get("name"), str) for c in competitors)


def _local_text_near_name(text: str, name: str) -> str:
    """The sentence(s) mentioning `name` plus the one right after each,
    instead of the whole shared source text - mirrors how _local_context
    scopes an NER entity's context, for the same reason and the same
    known limit: a single "Competitors" source snippet routinely names
    several competitors (e.g. a listicle), each with its own price/
    features stated nearby. Without this scoping, _estimate_price/
    _estimate_breadth ran over the *entire* source text and could pick up
    a different competitor's numbers - confirmed live: two competitors
    sharing one source, one cheap and one expensive, both came out with
    the cheaper one's price bucket, since _estimate_price just takes the
    cheapest amount found anywhere in the text it's given. This bounds
    that to at most the immediately-following sentence (the same
    comparison-table shape _local_context's own 2-sentence window exists
    for - a name on one line, its price on the very next), not a full
    source's worth of unrelated competitors' numbers; it can still bleed
    into a different competitor's price when that competitor's own line
    comes immediately after this one's, same tradeoff as _local_context.
    Falls back to the full text if the name can't be located in it
    (defensive only - callers already confirm a case-insensitive
    substring match exists before calling this).
    """
    sentences = [s for s in text.split(". ") if s]
    lowered_name = name.lower()
    matches = [". ".join(sentences[i : i + 2]) for i, s in enumerate(sentences) if lowered_name in s.lower()]
    return " ".join(matches) if matches else text


def _ground_and_clean_competitors(raw: list, sources: dict[str, dict]) -> list[dict]:
    """Keep only competitors the model can prove: a name is dropped unless
    it names a `sourceIds` entry we actually gave the model AND the name
    literally appears (case-insensitive) in that source's own text. This is
    the same rule `sanitize_source_ids`/`verification.py` apply to claims
    elsewhere in the pipeline, applied here to competitor names themselves -
    the model can restate and reason about what's in the sources, but can't
    add a competitor from its own training data. See
    docs/competitor-detection-and-confidence-scoring-proposal.md Option B.
    """
    cleaned: list[dict] = []
    seen_lower: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _short_text(item.get("name"), 80)
        if not name or name.lower() in seen_lower:
            continue
        source_ids = item.get("sourceIds")
        if not isinstance(source_ids, list):
            continue
        matching_ids = [
            sid
            for sid in source_ids
            if isinstance(sid, str) and sid in sources and name.lower() in sources[sid]["text"].lower()
        ]
        if not matching_ids:
            continue

        seen_lower.add(name.lower())
        primary_source = sources[matching_ids[0]]["result"]
        local_text = " ".join(_local_text_near_name(sources[sid]["text"], name) for sid in matching_ids)
        profile = _clean_profile(item)
        gap = profile.pop("gap")
        offering = _short_text(item.get("offering"), 200) or _clean_offering(
            (primary_source.get("snippet") or "").strip()
        )
        cleaned.append(
            {
                "name": name,
                "offering": offering or "See source for details.",
                "url": primary_source.get("url", ""),
                "gap": gap or _GAP_DISCLOSURE,
                **profile,
                "estimatedPrice": _estimate_price(local_text) or "unknown",
                "featureBreadth": _estimate_breadth(local_text) or "unknown",
                "_local_text": local_text,
            }
        )
        if len(cleaned) >= _MAX_COMPETITORS:
            break
    return cleaned


def _discover_with_llm(
    idea: str,
    target_customer: str,
    problem: str,
    results: list,
    ner_hint_names: list[str],
    allow_local: bool = False,
) -> dict | None:
    """One bounded LLM call that reads every "Competitors"-angle search
    result (not just the ones NER already tagged) and returns the real
    competitors named in them, each grounded back to the source it came
    from - see _ground_and_clean_competitors. This is what lets discovery
    find a competitor NER's small spaCy model missed entirely (a lowercase
    or unusual brand name, a name split oddly across sentences), instead of
    only ever decorating NER's own list as the old profiling pass did.

    Strictly additive: returns None on any failure (no competitor-angle
    results, quota exhausted, bad JSON, missing dependency) or when nothing
    survives grounding, and the caller keeps its NER-only result for those
    names, so this can never turn a working competitor section into a
    worse one, and never adds a call when `results` has no Competitors
    angle at all (e.g. web search itself failed).
    """
    competitor_results = [r for r in results if r.get("angle") == "Competitors"]
    if not competitor_results:
        return None
    try:
        from crewai import Agent, Crew, Process, Task

        from .llm import get_llm, kickoff_with_fallback
        from .prompts.loader import load_prompt
    except Exception:
        logger.warning("Competitor discovery unavailable (LLM stack not importable)", exc_info=True)
        return None

    sources: dict[str, dict] = {}
    listing_lines = []
    for i, r in enumerate(competitor_results, start=1):
        source_id = f"r{i}"
        text = _normalize_snippet_text(r.get("title", ""), r.get("snippet", ""))
        sources[source_id] = {"text": text, "result": r}
        listing_lines.append(f"{source_id}: {text[:600]}")
    listing = "\n".join(listing_lines)

    def build_crew(model: str):
        analyst = Agent(
            role="Competitive Intelligence Analyst",
            goal="Find every real competitor named in the given search results and profile each one strictly from its own text.",
            backstory=load_prompt("competitor_discovery_system"),
            llm=get_llm(max_tokens=1100, model=model),
            verbose=False,
        )
        task = Task(
            description=load_prompt(
                "competitor_discovery_task",
                idea=idea,
                target_customer=target_customer or "not specified",
                problem=problem or "not specified",
                listing=listing,
                ner_hints=", ".join(ner_hint_names) or "none",
                max_competitors=_MAX_COMPETITORS,
            ),
            expected_output=load_prompt("competitor_discovery_output"),
            agent=analyst,
        )
        return Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)

    try:
        output = kickoff_with_fallback(
            build_crew,
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_discovery_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_discovery_shape)
    except Exception:
        logger.warning("Competitor discovery failed, keeping NER-only competitors", exc_info=True)
        return None
    if data is None:
        return None

    grounded = _ground_and_clean_competitors(data["competitors"], sources)
    names = {c["name"] for c in grounded}
    return {
        "competitors": grounded,
        "comparisonMatrix": _clean_matrix(data.get("comparisonMatrix"), names) if names else [],
    }


def analyze_competitors(
    idea: str,
    target_customer: str,
    problem: str,
    results: list,
    profile: bool = False,
    allow_local: bool = False,
) -> dict:
    """Identify competitors from `results`.

    Base pass: local NER - no LLM call, no API dependency, so this never
    fails due to rate limits or provider outages. An empty `competitors: []`
    is a genuine, valid outcome (the sources didn't name any identifiable
    company), not a failure - matches the existing contract exactly, so the
    frontend's null-vs-empty distinction still works unchanged.

    With profile=True (the full "deep" pipeline), _discover_with_llm reads
    the same search results with an LLM and returns grounded competitors -
    including ones NER missed - plus richer per-competitor fields
    (classification, pricing, businessModel, strengths, weaknesses, a real
    idea-specific gap) and a comparisonMatrix. Its list is used first (it
    read strictly more of the source text and every name is grounding-
    checked); any NER name it didn't already cover is appended after it, up
    to _MAX_COMPETITORS, as a recall safety net - see
    docs/competitor-detection-and-confidence-scoring-proposal.md Option B.
    Any discovery failure (including "no Competitors-angle results at all")
    leaves this exactly as the old NER-only behavior, with "profiled":
    False whenever profile=True and the result is non-empty.

    A Gemini refinement pass (_refine_with_gemini) fills in the
    estimatedPrice/featureBreadth cells the regex heuristics (run for both
    NER and discovered competitors) left "unknown" - separate API key/
    quota from Groq, optional (skipped entirely without GEMINI_API_KEY),
    and never overrides a value already found, only fills genuine gaps.
    """
    if _nlp is None:
        return {"competitors": []}

    search_result_count = sum(1 for r in results if r.get("angle") == "Competitors")
    mentions = _extract_entities(results)
    kept_names = _dedupe_near_matches(mentions)

    discovered = (
        _discover_with_llm(idea, target_customer, problem, results, kept_names, allow_local=allow_local)
        if profile
        else None
    )
    discovered_competitors = discovered["competitors"] if discovered else []
    discovered_names_lower = {c["name"].lower() for c in discovered_competitors}

    remaining_slots = max(0, _MAX_COMPETITORS - len(discovered_competitors))
    ner_names = [n for n in kept_names if n.lower() not in discovered_names_lower][:remaining_slots]

    refinable = [
        {"name": c["name"], "text": c["_local_text"]}
        for c in discovered_competitors
        if c["estimatedPrice"] == "unknown" or c["featureBreadth"] == "unknown"
    ] + [
        {"name": name, "text": mentions[name]["local_text"]}
        for name in ner_names
        if mentions[name]["price"] is None or mentions[name]["breadth"] is None
    ]
    refinements = _refine_with_gemini(idea, refinable) if refinable else {}

    competitors = []
    for c in discovered_competitors:
        refined = refinements.get(c["name"], {})
        if c["estimatedPrice"] == "unknown":
            c["estimatedPrice"] = refined.get("price", "unknown")
        if c["featureBreadth"] == "unknown":
            c["featureBreadth"] = refined.get("featureBreadth", "unknown")
        del c["_local_text"]
        competitors.append(c)

    for name in ner_names:
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
                "classification": "unknown",
            }
        )

    _enrich_with_apis(competitors)

    result = {"competitors": competitors, "searchResultCount": search_result_count}
    if not profile or not competitors:
        return result

    matrix = discovered["comparisonMatrix"] if discovered else []
    # The LLM discovery pass is what would normally build this (see
    # competitor_discovery_task.md Step 3), but it's one more LLM call that
    # can fail/rate-limit/return nothing - which used to mean the whole
    # comparison view silently disappeared regardless of how good the
    # competitor list itself was. Falling back to a matrix built from data
    # this module already has (estimatedPrice/featureBreadth/classification)
    # means the comparison always renders whenever there are competitors to
    # compare against, independent of that one call's success - it's a
    # thinner matrix than the LLM's idea-specific one, never a missing one.
    result["comparisonMatrix"] = matrix if matrix else _build_fallback_matrix(competitors)
    result["profiled"] = discovered is not None
    return result
