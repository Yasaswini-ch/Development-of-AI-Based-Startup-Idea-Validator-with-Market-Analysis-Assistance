"""
Go-To-Market (GTM) Strategy Agent for Milestone 3.

Synthesizes strategic market positioning statements, primary acquisition channels,
and early customer outreach tactics derived from target customer demographics and market opportunity data.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_CHANNELS = 4


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def analyze_gtm_strategy(
    idea: str,
    target_customer: str,
    problem: str,
    market_opportunity: Optional[Dict[str, Any]] = None,
    competitors: Optional[Dict[str, Any]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Derive Go-To-Market strategy, positioning statement, and acquisition channels."""
    results = results or []
    market_opportunity = market_opportunity or {}
    competitors = competitors or {}

    customer = _clean(target_customer) or "Target Early Adopters"
    prob = _clean(problem) or "unresolved customer pain points"
    idea_clean = _clean(idea)

    # 1. Strategic Positioning Statement
    positioning = (
        f"For {customer} who experience {prob}, '{idea_clean}' is the focused "
        f"solution that provides immediate value through an automated, streamlined experience."
    )

    # 2. Key Customer Acquisition Channels
    channels = []
    
    # Check target customer keywords for targeted channel recommendations
    cust_lower = customer.lower()
    if "developer" in cust_lower or "engineer" in cust_lower or "tech" in cust_lower:
        channels.extend([
            "Developer Communities & Forums (GitHub, Hacker News, Reddit /r/programming)",
            "Technical Content Marketing & Documentation-led Growth",
        ])
    elif "student" in cust_lower or "academic" in cust_lower or "university" in cust_lower:
        channels.extend([
            "Campus Pitch Competitions & University Incubator Networks",
            "Student Founder Groups & Social Media (LinkedIn, Discord, X)",
        ])
    elif "business" in cust_lower or "b2b" in cust_lower or "saas" in cust_lower:
        channels.extend([
            "Outbound LinkedIn Outreach & B2B Industry Newsletters",
            "Product Hunt Launch & Vertical Industry Directory Listings",
        ])
    else:
        channels.extend([
            "Niche Online Communities & Focused Social Media Outreach",
            "Search Engine Optimization (SEO) targeting high-intent long-tail keywords",
        ])

    channels.append("Direct Referral Incentive Program for Early Adopters")

    # 3. Early Customer Approach Tactic
    early_customer_approach = (
        f"Conduct direct qualitative outreach to 20-30 high-intent {customer}. "
        f"Offer exclusive free beta access in exchange for structured feedback and baseline retention metrics."
    )

    return {
        "summary": f"Go-To-Market acquisition strategy and positioning for '{idea_clean[:40]}...'.",
        "positioning": positioning,
        "channels": channels[:_MAX_CHANNELS],
        "earlyCustomerApproach": early_customer_approach,
    }
