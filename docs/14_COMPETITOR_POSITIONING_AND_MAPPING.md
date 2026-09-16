# 14. Competitor Positioning & 3x3 Grid Engine Specification
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Verified & Operational  

---

## 📑 Document Table of Contents
- [1. Executive Summary & Design Rationale](#1-executive-summary--design-rationale)
- [2. Local spaCy NER Competitor Extraction](#2-local-spacy-ner-competitor-extraction)
- [3. Entity Filtering & Product Context Rules](#3-entity-filtering--product-context-rules)
- [4. Pricing & Feature Breadth Classification Heuristics](#4-pricing--feature-breadth-classification-heuristics)
- [5. 3x3 Positioning Grid Algorithm](#5-3x3-positioning-grid-algorithm)

---

## 1. Executive Summary & Design Rationale

In early iterations of Affinity, Competitor Discovery was executed by an LLM agent using CrewAI. Live load testing revealed that relying on LLMs for competitor extraction resulted in severe token quota exhaustion and frequent entity hallucinations (e.g. returning generic terms like "Software", "Platform", or outdated entities).

[`backend/agent/competitor_agent.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/competitor_agent.py) solves this by using **local spaCy Named Entity Recognition (NER)** (`en_core_web_sm`). This non-LLM approach achieves:
- **$0.00 API Token Cost** per competitor extraction.
- **Zero Rate-Limit Overhead**, saving 100% of LLM quota for Market Opportunity analysis.
- **Factual Grounding**, extracting company and product names directly from live search text.

---

## 2. Local spaCy NER Competitor Extraction

```mermaid
flowchart LR
    Snippets["Retrieved Search Snippets"] --> Normalization["1. Join Lines with '. ' (Sentence Boundaries)"]
    Normalization --> NER["2. spaCy en_core_web_sm (Extract ORG Entities)"]
    NER --> Denylist["3. Filter Platform & Generic Denylist"]
    Denylist --> ContextValidation["4. _has_product_context() Validation"]
    ContextValidation --> LocalHeuristic["5. Extract Price & Breadth from Local Context"]
    LocalHeuristic --> Grid["6. Render 3x3 Positioning Grid"]
```

### Line Normalization Fix
A critical bug fix (`046468f`) addressed scraped comparison table snippets. Joining scraped listicle lines with spaces allowed spaCy to merge adjacent lines into garbled multi-word entities. Joining lines with `". "` establishes explicit sentence boundaries, enabling spaCy to identify real competitors cleanly.

---

## 3. Entity Filtering & Product Context Rules

To prevent false positives, `competitor_agent.py` applies three layers of filtering:

### 3.1 Generic Term Denylist (`_GENERIC_WORDS`)
Strips out platform keywords, UI terms, and generic nouns mislabeled as `ORG`:
```python
_GENERIC_WORDS = {
    "android", "ios", "pdf", "reply", "ai", "app", "apps", "software",
    "ratings", "awards", "history", "newsweek", "cbt", "windows", "journal"
}
```

### 3.2 Product Context Validation (`_has_product_context`)
Single-word, non-camelCase candidate entities are accepted **only** if product-ish context (`app`, `software`, `pricing`, `monthly`, `alternative`, `platform`, `tool`) exists nearby in at least one mention:

```python
def _has_product_context(name: str, doc) -> bool:
    for ent in doc.ents:
        if ent.text.strip().lower() == name.lower():
            sentence = ent.sent.text.lower()
            if any(term in sentence for term in _PRODUCT_TERMS):
                return True
    return False
```

- **camelCase Exception:** Distinct multi-word or camelCase names (e.g., `HelloFresh`, `RocketMoney`, `FreshBooks`) bypass the single-word context check.

---

## 4. Pricing & Feature Breadth Classification Heuristics

Rather than guessing prices, Affinity extracts pricing and breadth metrics strictly from the competitor's 2-sentence local text snippet.

### 4.1 Price Classification (`_estimate_price`)
Matches dollar amounts ($) and explicit period keywords (`/month`, `per year`, `a month`, `a year`):
- **`low`:** Pricing under **$15/month** or **$150/year**.
- **`mid`:** Pricing between **$15/month – $50/month** ($150 – $500/year).
- **`high`:** Pricing exceeding **$50/month** or **$500/year**.
- **`unknown`:** If no explicit pricing period match is found in the local context.

### 4.2 Feature Breadth Classification (`_estimate_breadth`)
Pattern-matches feature keywords in local text:
- **`narrow`:** Matches `niche`, `specialized`, `single-feature`, `simple`, `focused`.
- **`broad`:** Matches `all-in-one`, `comprehensive`, `full-suite`, `platform`, `enterprise`.
- **`moderate`:** Default fallback when feature evidence exists without extreme keywords.
- **`unknown`:** If no feature description is available in local text.

---

## 5. 3x3 Positioning Grid Algorithm

Competitors are rendered on a 3x3 matrix in [`frontend/src/components/CompetitorAnalysis.jsx`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/frontend/src/components/CompetitorAnalysis.jsx):

```text
               Narrow Breadth     Moderate Breadth     Broad Breadth
High Price   [  Competitor  ]   [  Competitor  ]   [  Competitor  ]
Mid Price    [  Competitor  ]   [  Competitor  ]   [  FreshBooks  ]
Low Price    [  Competitor  ]   [  Competitor  ]   [  Competitor  ]
```

- **Unplaced Competitors:** Competitors with `"unknown"` price or breadth are listed cleanly below the grid rather than being placed arbitrarily.
- **Positioning White-Space:** Empty grid cells highlight direct structural market opportunities for founders.
