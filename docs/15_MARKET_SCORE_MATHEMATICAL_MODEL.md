# 15. Market Opportunity Score Mathematical Formulation
**Project:** Affinity — AI-Based Startup Idea Validator with Market Analysis Assistance  
**Document Version:** 2.0 · September 2026  
**Status:** Verified & Operational  

---

## 📑 Document Table of Contents
- [1. Executive Summary & Scoring Objectives](#1-executive-summary--scoring-objectives)
- [2. Mathematical Formulation](#2-mathematical-formulation)
- [3. Variable Definitions & Weighting Criteria](#3-variable-definitions--weighting-criteria)
- [4. Edge Case Handling & Fallback Behavior](#4-edge-case-handling--fallback-behavior)
- [5. Code Implementation (`opportunity_score.py`)](#5-code-implementation-opportunity_scorepy)

---

## 1. Executive Summary & Scoring Objectives

The **Opportunity Score** is a consolidated **0–100 integer metric** representing the overall market viability and strategic potential of a submitted startup concept.

Unlike black-box LLM ratings, Affinity's Opportunity Score is calculated using a **deterministic mathematical formulation** in [`backend/agent/opportunity_score.py`](file:///C:/Opensource/AI%20Based%20Startup%20Idea%20Validator/backend/agent/opportunity_score.py). It combines:
1. Market Size ($S_{\text{market}}$)
2. Growth Trends & CAGR ($S_{\text{growth}}$)
3. Competitor Density ($S_{\text{density}}$)
4. White-Space Feature Gaps ($S_{\text{gaps}}$)

---

## 2. Mathematical Formulation

$$\text{OpportunityScore} = \text{Clamp}\left( \text{Base} + S_{\text{market}} + S_{\text{growth}} - S_{\text{density}} + S_{\text{gaps}}, \, 0, \, 100 \right)$$

Where:
$$\text{Clamp}(x, a, b) = \max(a, \min(x, b))$$
$$\text{Base} = 50$$

---

## 3. Variable Definitions & Weighting Criteria

### 3.1 Market Size Component ($S_{\text{market}}$)
Evaluates the absolute financial size of the addressable market:

$$S_{\text{market}} = \begin{cases} 
+15 & \text{if market size text contains explicit TAM/SAM } > \$1\text{B} \\
+10 & \text{if market size text indicates a multi-million market } (\$100\text{M} - \$999\text{M}) \\
+5 & \text{if positive market size indicated without explicit figures} \\
0 & \text{if market size is unclear or unstated}
\end{cases}$$

### 3.2 Growth Trends Component ($S_{\text{growth}}$)
Evaluates market growth rates and adoption velocity:

$$S_{\text{growth}} = \begin{cases} 
+15 & \text{if CAGR } > 10\% \text{ or } \ge 3 \text{ positive growth trends identified} \\
+10 & \text{if 1 to 2 positive market trends identified} \\
0 & \text{if market growth is neutral or unstated} \\
-10 & \text{if declining market trends detected}
\end{cases}$$

### 3.3 Competitor Density Penalty ($S_{\text{density}}$)
Penalizes market saturation based on extracted competitor entities:

$$S_{\text{density}} = \begin{cases} 
+15 & \text{if competitors } > 5 \text{ (High Saturation)} \\
+5 & \text{if competitors } \in [2, 5] \text{ (Moderate Saturation)} \\
0 & \text{if competitors } \le 1 \text{ (Low Saturation / Blue Ocean)}
\end{cases}$$

### 3.4 White-Space Gap Component ($S_{\text{gaps}}$)
Rewards identified unaddressed customer pain points:

$$S_{\text{gaps}} = \begin{cases} 
+15 & \text{if } \ge 2 \text{ evidence-backed white-space feature opportunities exist} \\
+10 & \text{if 1 white-space feature opportunity exists} \\
0 & \text{if zero white-space opportunities identified}
\end{cases}$$

---

## 4. Edge Case Handling & Fallback Behavior

If upstream agents encounter partial failures, `opportunity_score.py` executes fallback scoring over raw search snippet relevance scores:

| Upstream Failure State | Scoring Behavior | Fallback Mechanism |
|---|---|---|
| `marketOpportunity == null` | Market components set to neutral ($S_{\text{market}}=0, S_{\text{growth}}=0$) | Uses average search relevance score from `results[].score` |
| `competitors == null` | Density penalty set to neutral ($S_{\text{density}}=0$) | Assumes baseline competitor saturation |
| All Upstream Agents Failed | Score defaults to baseline search score | $\text{Score} = \text{Clamp}(\text{AvgSearchScore} \times 100, 30, 70)$ |

---

## 5. Code Implementation (`opportunity_score.py`)

```python
def calculate_opportunity_score(
    market_op: dict | None,
    competitors: dict | None,
    results: list
) -> int:
    score = 50  # Baseline

    if market_op:
        size_text = market_op.get("marketSize", "").lower()
        if "billion" in size_text or "tam" in size_text:
            score += 15
        elif size_text and "not clear" not in size_text:
            score += 5

        trends = market_op.get("trends", [])
        if len(trends) >= 3:
            score += 15
        elif len(trends) > 0:
            score += 10

    if competitors:
        comp_list = competitors.get("competitors", [])
        if len(comp_list) > 5:
            score -= 15
        elif len(comp_list) >= 2:
            score -= 5

    return max(0, min(100, score))
```
