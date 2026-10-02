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

from . import web_cache
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
    # Page chrome and non-competitors that real runs surfaced as "rivals": a
    # browser named in "Chrome extension", the "Key Features" heading of a
    # product page, and the review/analyst sites a "best X software" article is
    # published on (Capterra, G2 ...). A review site is a source, not a rival.
    "chrome", "firefox", "safari", "features", "feature", "capterra", "g2", "trustpilot",
    "trustradius", "gartner", "forrester", "pcmag", "techradar", "cnet",
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
    # Confirmed live (Sept 2026, water-bottle-idea test run): same
    # publisher-citing-a-product pattern as the outlets above, this time a
    # tech-news site the earlier denylist pass didn't happen to cover.
    "nocamels",
}

# Role/title words that, immediately before a capitalized span, signal
# "this is a person's name from a bio/attribution line" rather than a
# company - e.g. "CEO: Cyril Xinyi HAN" on a "Top 10 Super Apps" listicle.
# Confirmed live (Sept 2026, fintech-bill-negotiation-idea test run): that
# exact "CEO: <name>" line got NER-tagged ORG and surfaced as a
# "competitor." Distinct from _GENERIC_WORDS (which catches mislabeled
# generic text) - this catches a correctly-parsed real name that's simply
# not a company at all.
_PERSON_ATTRIBUTION_WORDS = {
    "ceo", "founder", "co-founder", "cofounder", "president", "director",
    "cto", "coo", "cfo", "chairman", "chairwoman",
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
    if any(w in _GENERIC_WORDS for w in words):
        return True
    # "Development & IT", "Design & Creative" - a marketplace's own category
    # nav (Freelancer.com, Toptal, Upwork all list these) reads to spaCy's
    # ORG tagger exactly like a two-word brand joined by "&", and the two
    # words on either side are whatever the site's category taxonomy calls
    # its skill categories - too open-ended to denylist word by word the
    # way _GENERIC_WORDS does. Confirmed live: both category labels above
    # surfaced as "competitors" for a freelancer-invoicing idea. A real
    # brand containing "&" (AT&T, Proctor & Gamble) is rare enough in this
    # context that the false-negative cost is worth it.
    return "&" in name



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


# Byline/author-credit chrome that scrapes with zero whitespace between a
# name and the word right after it - "Aasif KhanWritten byAasif Khan...",
# "Abhinav GirdharLast updated onSeptember 2" - confirmed live (Sept 2026,
# a "10 Best Apps" listicle). These fuse into a camelCase-looking span
# ("KhanWritten", "GirdharLast") that passes as a real two-part brand name
# on a single mention, exactly like "HelloFresh" is trusted to - the
# byline text isn't malformed HTML, the site's own markup just renders
# "Written by", "Reviewed by", "Last updated on" immediately adjacent to
# the name with no separating space at all.
_BYLINE_CHROME_WORDS = {"written", "reviewed", "updated", "edited", "published", "posted", "last"}


def _is_byline_merge(name: str) -> bool:
    segments = _CAMEL_SPLIT.findall(name)
    return bool(segments) and segments[-1].lower() in _BYLINE_CHROME_WORDS


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


def _is_person_attribution(doc, ent) -> bool:
    """True when a role/title word (see _PERSON_ATTRIBUTION_WORDS) sits in
    the short span of text right before this entity - "CEO: Cyril Xinyi
    HAN", "Founder, Jane Smith". A short character window (not just "the
    previous word") because a colon, comma, or extra whitespace commonly
    sits between the role word and the name itself.
    """
    start = max(0, ent.start_char - 25)
    preceding_words = {w.strip(":,.()") for w in doc.text[start:ent.start_char].lower().split()}
    return bool(preceding_words & _PERSON_ATTRIBUTION_WORDS)


_REVIEW_DATE_PATTERN = re.compile(r"^\s*\.?\s*\d{1,2}/\d{1,2}/\d{2,4}\b")


def _is_review_byline(doc, ent) -> bool:
    """True when the entity is immediately followed by a date in
    M/D/YYYY-style form - "Dakota MarTin. 09/10/2026. Works great!" - the
    exact shape a scraped customer-review section produces (reviewer name,
    review date, review text run together with no real separator).
    Confirmed live (Sept 2026, water-bottle-idea test run): this got
    NER-tagged ORG and surfaced as a "competitor" despite having no role
    word nearby for _is_person_attribution to catch - a distinct pattern,
    not a variant of the same one.
    """
    following = doc.text[ent.end_char : ent.end_char + 15]
    return bool(_REVIEW_DATE_PATTERN.match(following))


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
            if _is_person_attribution(doc, ent) or _is_review_byline(doc, ent):
                continue
            if _is_duplicated_merge(name) or _is_byline_merge(name):
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
        lowered = name.lower()
        # Case-insensitive: "Toptal" and "TopTal" are one company, and were kept
        # as two rivals when this compared exact spellings.
        if any(lowered in k.lower() or k.lower() in lowered for k in kept):
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
_MAX_LIST_ITEMS = 5
_LISTING_CHARS_FULL = 2500
_MAX_MATRIX_ROWS = 8


def _short_text(value, limit: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] if cleaned else None


def _short_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_short_text(v, 200) for v in value]
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
        "pricing": _short_text(raw.get("pricing"), 150) or "unknown",
        "businessModel": _short_text(raw.get("businessModel"), 150) or "unknown",
        "strengths": _short_list(raw.get("strengths")),
        "weaknesses": _short_list(raw.get("weaknesses")),
        "gap": _short_text(raw.get("gap"), 400),
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
        dimension = _short_text(row.get("dimension"), 100)
        idea_cell = _short_text(row.get("idea"), 300)
        cells = row.get("competitors")
        if not dimension or not idea_cell or not isinstance(cells, dict):
            continue
        rows.append(
            {
                "dimension": dimension,
                "idea": idea_cell,
                "competitors": {
                    name: _short_text(cells.get(name), 300) or "unknown" for name in names if name in cells
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


_MATRIX_MIN_ROWS = 6
_MATRIX_MAX_COMPETITOR_COLUMNS = 8
_PRE_LAUNCH = "Not yet - pre-launch"


def _known(value) -> bool:
    return bool(value) and str(value).strip().lower() not in {"unknown", "n/a", "see source for details."}


def _matrix_competitors(competitors: list[dict]) -> list[dict]:
    """The rivals worth a column: direct before indirect before unlabelled
    (stable within each), at most _MATRIX_MAX_COMPETITOR_COLUMNS. A table with
    every rival found (up to 20) is unreadable."""
    order = {"direct": 0, "indirect": 1}
    ranked = sorted(competitors, key=lambda c: order.get(c.get("classification"), 2))
    return ranked[:_MATRIX_MAX_COMPETITOR_COLUMNS]


def _rating_text(competitor: dict) -> str:
    enrichment = competitor.get("enrichment") or {}
    rating, count = enrichment.get("averageRating"), enrichment.get("ratingCount")
    if not rating:
        return "unknown"
    text = f"{float(rating):.1f}/5"
    return f"{text} from {int(count):,} ratings" if count else text


def _candidate_rows(competitors: list[dict], idea: str) -> list[tuple[str, str, dict, bool]]:
    """(dimension, idea cell, {competitor: cell}, always_show) for every row
    that can be built from fields this module already holds - nothing here is
    invented, and the idea's own side stays honest about being pre-launch."""
    first = (idea or "").strip().split(". ")[0].strip()[:200]

    def cells(fn):
        return {c["name"]: fn(c) or "unknown" for c in competitors}

    def first_item(key):
        return lambda c: (c.get(key) or [None])[0]

    return [
        ("Price", "Not yet priced - pre-launch", cells(lambda c: _PRICE_LABELS[c.get("estimatedPrice", "unknown")]), True),
        ("Feature breadth", "Not yet built - pre-launch", cells(lambda c: _BREADTH_LABELS[c.get("featureBreadth", "unknown")]), True),
        ("Positioning", "New entrant addressing this need", cells(lambda c: _CLASSIFICATION_LABELS[c.get("classification", "unknown")]), True),
        ("What it offers", first or "See the idea above", cells(lambda c: c.get("offering") if _known(c.get("offering")) else None), False),
        ("Business model", "Not yet decided - pre-launch", cells(lambda c: c.get("businessModel") if _known(c.get("businessModel")) else None), False),
        ("Main strength", "Not yet proven - pre-launch", cells(first_item("strengths")), False),
        ("Main weakness", "Not yet known - pre-launch", cells(first_item("weaknesses")), False),
        ("Customer rating", "No users yet - pre-launch", cells(lambda c: _rating_text(c) if _known(_rating_text(c)) else None), False),
        ("Pricing details", "Not yet priced - pre-launch", cells(lambda c: c.get("pricing") if _known(c.get("pricing")) else None), False),
        (
            "Founded",
            "New",
            cells(lambda c: str((c.get("enrichment") or {}).get("foundedYear") or "") or None),
            False,
        ),
    ]


def _build_fallback_matrix(competitors: list[dict], idea: str = "") -> list[dict]:
    """A deterministic comparisonMatrix built only from fields this module
    already holds for every competitor - used whenever the LLM discovery pass
    didn't produce one (it wasn't run, timed out, or found nothing), so the
    comparison view isn't contingent on that one call succeeding. It is
    honest about the idea's own side: pre-launch, there is no real price or
    shipped feature set to compare with, so those cells say exactly that
    instead of inventing one (same fabricate-nothing rule as _GAP_DISCLOSURE).

    Price, Feature breadth and Positioning are always shown. Further rows
    (what it offers, business model, pricing details, main strength, main
    weakness, customer rating, founded) appear only when at least one rival
    has real data for them, up to 8 rows in all. Columns are the closest
    rivals, at most 8.
    """
    if not competitors:
        return []
    shown = _matrix_competitors(competitors)
    rows = []
    for dimension, idea_cell, cells, always in _candidate_rows(shown, idea):
        if not always and not any(_known(v) for v in cells.values()):
            continue
        rows.append({"dimension": dimension, "idea": idea_cell, "competitors": cells})
        if len(rows) >= _MAX_MATRIX_ROWS:
            break
    return rows


def _pad_matrix(matrix: list[dict], competitors: list[dict], idea: str = "") -> list[dict]:
    """Top up a short model-written matrix to at least _MATRIX_MIN_ROWS rows
    with rule-based rows for dimensions it does not already cover, using the
    same competitors the model's rows describe. Model rows come first and are
    never altered."""
    if not matrix or len(matrix) >= _MATRIX_MIN_ROWS:
        return matrix
    names = {name for row in matrix for name in row.get("competitors", {})}
    shown = [c for c in competitors if c["name"] in names]
    if not shown:
        return matrix
    present = " | ".join(row["dimension"].lower() for row in matrix)
    padded = list(matrix)
    for dimension, idea_cell, cells, _always in _candidate_rows(shown, idea):
        if len(padded) >= _MATRIX_MIN_ROWS:
            break
        key = dimension.lower().split()[0]
        if key in present or not any(_known(v) for v in cells.values()):
            continue
        padded.append({"dimension": dimension, "idea": idea_cell, "competitors": cells})
    return padded


_MAX_ENRICHED = 8  # was 4; the comparison table shows up to 8 rivals and a rating row, and lookups are cached
_WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
_WIKIDATA_FOUNDING_YEAR = re.compile(r"\b(1[89]\d{2}|20[0-4]\d)\b")
_PRODUCTHUNT_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"
_ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
# Wikimedia's User-Agent policy (meta.wikimedia.org/wiki/User-Agent_policy)
# rejects requests with no identifying User-Agent - see _wikidata_lookup.
_WIKIMEDIA_USER_AGENT = "AffinityStartupValidator/1.0 (contact: infyteamnova@gmail.com)"


def _itunes_lookup(name: str) -> dict | None:
    """A free, keyless enrichment source for consumer-app competitors:
    Apple's public iTunes Search API. Unlike Wikidata (which only covers
    well-known/established companies) or Product Hunt (which needs a
    developer token and only indexes what's been submitted there), this
    covers any app actually published to the App Store - including small,
    recent competitors that are exactly the ones a new idea is most likely
    to be up against.

    Returns rating count and price, which double as a live-vs-abandoned
    signal: an app with a real rating count is demonstrably installed and
    used, not just a listed name. Best-effort like the other lookups here -
    returns None on any failure or no match, never raises.

    Confirmed live: for a name with no real match, iTunes' own search still
    returns *something* (its ranking always returns its closest fuzzy hits,
    never an empty list for a plausible-looking query) - e.g. a nonsense
    name returned an unrelated Arabic-language app as the top hit. Requiring
    the candidate's own name to actually be contained in the queried name's
    match - same "don't trust a loose match" rule _wikidata_lookup already
    applies - closes this without losing real matches: a genuine app's
    trackName is virtually always a superset of the name it's known by
    (e.g. "Rocket Money - Bills & Budgets" contains "Rocket Money").
    """
    try:
        url = f"{_ITUNES_SEARCH_URL}?{urllib.parse.urlencode({'term': name, 'entity': 'software', 'limit': 5})}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = json.loads(resp.read())
        results = body.get("results") or []
        needle = name.strip().lower()
        match = next(
            (
                r for r in results
                if needle and needle in r.get("trackName", "").strip().lower()
            ),
            None,
        )
        if not match:
            return None
        return {
            "source": "itunes",
            "trackName": match.get("trackName"),
            "price": match.get("formattedPrice") or ("Free" if match.get("price") == 0 else None),
            "averageRating": match.get("averageUserRating"),
            "ratingCount": match.get("userRatingCount"),
            "artworkUrl": match.get("artworkUrl100"),
            "url": match.get("trackViewUrl"),
        }
    except Exception:
        logger.warning("iTunes enrichment unavailable for %r", name, exc_info=True)
        return None


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

    Requires a descriptive User-Agent header - confirmed live: every call
    was failing with HTTP 403 because urllib's default "Python-urllib/3.x"
    User-Agent is exactly what Wikimedia's User-Agent policy
    (meta.wikimedia.org/wiki/User-Agent_policy) blocks to keep out
    unidentified bot traffic.
    """
    try:
        search_url = (
            f"{_WIKIDATA_SEARCH_URL}?action=wbsearchentities&search="
            f"{urllib.parse.quote(name)}&language=en&type=item&limit=1&format=json"
        )
        request = urllib.request.Request(
            search_url, headers={"User-Agent": _WIKIMEDIA_USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=5) as resp:
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


def _producthunt_search(query: str, first: int) -> list[dict] | None:
    """Product Hunt v2 GraphQL `posts(query: $name)` full-text search, most
    voted first. Returns the post nodes, or None when there is no token or
    the request/shape fails - best effort, never raises. The variable must
    be both declared and used in the query body (an unused `$name` is
    invalid GraphQL)."""
    token = os.environ.get("PRODUCTHUNT_API_TOKEN")
    if not token:
        return None
    try:
        request = urllib.request.Request(
            _PRODUCTHUNT_ENDPOINT,
            data=json.dumps(
                {
                    "query": (
                        "query SearchProduct($name: String!, $first: Int!) { "
                        "posts(query: $name, first: $first, order: VOTES) { "
                        "edges { node { name tagline votesCount website url } } } }"
                    ),
                    "variables": {"name": query, "first": first},
                }
            ).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=5) as resp:
            body = json.loads(resp.read())
        edges = body.get("data", {}).get("posts", {}).get("edges") or []
        return [e["node"] for e in edges if e.get("node")]
    except Exception:
        logger.warning("Product Hunt search unavailable for %r", query, exc_info=True)
        return None


def _producthunt_lookup(name: str) -> dict | None:
    """Enrichment for one already-named competitor: keeps a Product Hunt
    result only on an exact case-insensitive name match (a different
    product's tagline/votes on a competitor card is worse than none).
    Requires PRODUCTHUNT_API_TOKEN; None on no token, no match or any
    failure - can never break competitor discovery."""
    nodes = _producthunt_search(name, 5)
    match = next((n for n in nodes or [] if (n.get("name") or "").strip().lower() == name.strip().lower()), None)
    if not match:
        return None
    return {
        "source": "producthunt",
        "tagline": match.get("tagline"),
        "votesCount": match.get("votesCount"),
        "website": match.get("website"),
        "url": match.get("url"),
    }


_MAX_SIMILAR_PRODUCTS = 5


def _similar_products(idea: str, exclude_names: list[str]) -> list[dict]:
    """Products on Product Hunt that match the idea itself (a search on the
    idea text, not on a competitor name), excluding ones already listed as
    competitors. Shown separately from `competitors` on purpose: these are
    Product Hunt's own search hits, not names grounded in this run's search
    snippets, so they never feed the Opportunity Score or the comparison
    grid. [] without a token or on any failure."""
    query = " ".join((idea or "").split())[:100]
    if not query:
        return []
    taken = {n.strip().lower() for n in exclude_names}
    seen: set[str] = set()
    similar = []
    for node in _producthunt_search(query, _MAX_SIMILAR_PRODUCTS + len(taken)) or []:
        name = (node.get("name") or "").strip()
        key = name.lower()
        if not name or key in taken or key in seen:
            continue
        seen.add(key)
        similar.append(
            {
                "name": name,
                "tagline": node.get("tagline"),
                "votesCount": node.get("votesCount"),
                "website": node.get("website"),
                "url": node.get("url"),
            }
        )
        if len(similar) >= _MAX_SIMILAR_PRODUCTS:
            break
    return similar


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

    Order matters: Product Hunt needs a token most deployments won't have
    configured, so iTunes (keyless, and covers small/recent apps neither
    Product Hunt nor Wikidata's "notable enough for an encyclopedia" bar
    reaches) is tried before falling back to Wikidata's broader,
    non-software-specific company coverage.
    """
    for competitor in competitors[:_MAX_ENRICHED]:
        name = competitor["name"]
        # Company facts rarely change, so a name already looked up (for this or
        # any earlier idea) is reused for 30 days instead of calling three APIs.
        enrichment = web_cache.get("enrichment", name.strip().lower())
        if not enrichment:
            enrichment = _producthunt_lookup(name) or _itunes_lookup(name) or _wikidata_lookup(name)
            web_cache.put("enrichment", name.strip().lower(), enrichment)
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
    Falls back to the full text if the name can't be located in it - no
    longer purely defensive since _ground_and_clean_competitors stopped
    requiring a literal substring match (Sept 2026), so a genuinely
    ungrounded name (real, but not spelled out in this specific source)
    hits this fallback in normal operation, not just as an edge case.
    """
    sentences = [s for s in text.split(". ") if s]
    lowered_name = name.lower()
    matches = [". ".join(sentences[i : i + 2]) for i, s in enumerate(sentences) if lowered_name in s.lower()]
    return " ".join(matches) if matches else text


def _ground_and_clean_competitors(raw: list, sources: dict[str, dict]) -> list[dict]:
    """Keep competitors that cite a real source we actually gave the model -
    a name is dropped unless it names at least one `sourceIds` entry that
    exists in `sources`. Deliberately does NOT require the name to
    literally appear in that source's own text (relaxed by product
    decision, Sept 2026): the stricter substring check was dropping real,
    correct competitors the model recognized from general knowledge of the
    category even when a specific snippet didn't happen to spell the name
    out verbatim - the same tradeoff team-forge's competitor agent makes.
    Every kept competitor still points at a real URL a user can click to
    check for themselves; what changed is only that the specific name
    isn't re-verified against that page's text.
    """
    cleaned: list[dict] = []
    seen_lower: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _short_text(item.get("name"), 80)
        if not name or name.lower() in seen_lower or _is_generic_phrase(name):
            continue
        source_ids = item.get("sourceIds")
        if not isinstance(source_ids, list):
            continue
        matching_ids = [sid for sid in source_ids if isinstance(sid, str) and sid in sources]
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

        from .llm import AGENT_MAX_EXECUTION_SECONDS, AGENT_MAX_ITER, get_llm, kickoff_with_fallback, primary_for
        from .prompts.loader import load_prompt
    except Exception:
        logger.warning("Competitor discovery unavailable (LLM stack not importable)", exc_info=True)
        return None

    sources: dict[str, dict] = {}
    listing_lines = []
    for i, r in enumerate(competitor_results, start=1):
        source_id = f"r{i}"
        full_text = r.get("fullText")
        text = _normalize_snippet_text(r.get("title", ""), full_text or r.get("snippet", ""))
        sources[source_id] = {"text": text, "result": r}
        # 1500, not 600: a competitor mentioned deeper in a longer article
        # was invisible to the model at the old budget - team-forge's own
        # competitor prompt uses the same 1500-char window per source for
        # the same reason (its own comment: names mentioned deeper in
        # articles were getting truncated out at 200-300 chars).
        # A source with full page text (Tavily Extract) gets a bigger window.
        listing_lines.append(f"{source_id}: {text[:_LISTING_CHARS_FULL if full_text else 1500]}")
    listing = "\n".join(listing_lines)

    def build_crew(model: str):
        analyst = Agent(
            role="Competitive Intelligence Analyst",
            goal="Find every real competitor named in the given search results and profile each one strictly from its own text.",
            backstory=load_prompt("competitor_discovery_system"),
            # 950, not 1100: qwen/qwen3.8-27b (the primary/first model tried)
            # enforces a hard 1000 output-tokens/minute ceiling - confirmed
            # live, "Request too large... Requested 1100... exceed the
            # enforced limit" fails on every single call regardless of
            # remaining quota, not a transient rate limit. 950 leaves
            # headroom under that ceiling; the fallback models have far
            # higher per-minute budgets so this doesn't meaningfully
            # constrain them.
            llm=get_llm(max_tokens=950, model=model),
            max_execution_time=AGENT_MAX_EXECUTION_SECONDS,
            max_iter=AGENT_MAX_ITER,
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
            # Own lane, separate from market/swot/mvp's shared default
            # (qwen3.8-27b): this call now asks for noticeably more output
            # per competitor (richer offering/gap text, up to 8 matrix
            # rows) than it used to, on top of already being the most
            # quota-hungry call some nights - giving it its own Groq model
            # bucket keeps that growth from crowding out the other
            # sequential pipeline agents.
            primary=primary_for("competitor"),
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


_MIN_OVERLAP_FOR_DIRECT = 2


# Words that appear on almost any page about almost any idea, so matching
# them says nothing about whether a competitor does the same *job* - found
# live: "time", "hours", "clients" made every competitor of a freelancer
# invoicing idea look direct.
_GENERIC_TOPIC_STEMS = {
    "time", "hour", "client", "customer", "user", "people", "business",
    "work", "day", "way", "need", "tool", "app", "platform", "service",
}


def _stem(word: str) -> str:
    """Crude suffix strip so "invoice"/"invoices"/"invoicing" count as one
    topic instead of three separate matches."""
    w = word.lower()
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            return w[: -len(suffix)]
    return w


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[A-Za-z]{3,}", text)}


def _classify_competitor(
    idea_keywords: set[str], competitor_text: str, exclude_terms: str = ""
) -> str:
    """Deterministic direct/indirect label from how many distinct *job*
    topics of the idea (e.g. invoicing, payments, tracking) a competitor's
    own text covers - the fallback path's substitute for the LLM's
    classification, which it otherwise lacks.

    "direct" needs 2+ distinct topics, "indirect" exactly 1, "unknown" none.
    Three things keep it from calling everything direct, which is what it
    did before: variants collapse to one stem, the customer's own words
    (`exclude_terms`, e.g. "freelancers") and generic words are ignored
    because every page about the audience contains them, and callers should
    pass only the competitor's own sentence(s), not the whole shared
    listicle snippet it was found in.

    Still textual overlap, not the reasoning an LLM does ("same customer,
    same problem") - treat it as a rough signal.
    """
    ignore = _GENERIC_TOPIC_STEMS | _stems(exclude_terms)
    topic_stems = {s for s in (_stem(k) for k in idea_keywords) if s not in ignore}
    if not topic_stems:
        return "unknown"
    matched = len(topic_stems & _stems(competitor_text))
    if matched >= min(_MIN_OVERLAP_FOR_DIRECT, len(topic_stems)):
        return "direct"
    if matched >= 1:
        return "indirect"
    return "unknown"


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

    # Wide net (8, not the usual 3) since this only needs to catch overlap,
    # not produce a short display phrase - see _classify_competitor. Lazy
    # import to avoid a circular import: retrieval.py itself does
    # `from .competitor_agent import _nlp` at its own module level, so
    # importing retrieval.py from here at module load time would resolve
    # before this module's own `_nlp` is defined, silently leaving
    # retrieval.py's `_nlp` (and therefore _distinctive_nouns) permanently
    # None - confirmed live: every classification came back "unknown"
    # because of exactly this until the import was made lazy.
    from .retrieval import _distinctive_nouns

    idea_keywords = set(_distinctive_nouns(f"{idea} {problem}", max_words=8))

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
                "classification": _classify_competitor(
                    idea_keywords, info["local_text"], exclude_terms=target_customer
                ),
            }
        )

    _enrich_with_apis(competitors)

    result = {"competitors": competitors, "searchResultCount": search_result_count}
    similar = _similar_products(idea, [c["name"] for c in competitors])
    if similar:
        result["similarProducts"] = similar
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
    result["comparisonMatrix"] = _pad_matrix(matrix, competitors, idea) if matrix else _build_fallback_matrix(competitors, idea)
    result["profiled"] = discovered is not None
    return result
