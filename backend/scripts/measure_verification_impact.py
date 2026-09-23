"""One-off measurement: how many claims does the verification pass (see
agent/verification.py) actually strip a citation from? Runs each sample
idea's real web-search results through the strategy agents twice - once
with verification disabled (monkeypatched to always say "supported"), once
with it enabled - and counts how many previously-cited claims lost their
citation. This is a measured number for THIS pipeline against real live
data, not an industry-average guess.

Requires a working GROQ_API_KEY (loads backend/.env). Makes real API
calls - each idea costs roughly 8 LLM calls (4 agents x2 for before/after,
plus up to 4 verification calls in the "after" pass), so this is
deliberately a small, explicit sample, not something to run casually or in
CI.

Usage: python scripts/measure_verification_impact.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from agent import gtm_agent, market_agent, mvp_agent, retrieval, swot_agent  # noqa: E402

IDEAS = [
    ("A budgeting app for freelancers with irregular income", "Freelancers", "Hard to budget with inconsistent monthly income"),
    ("A subscription box for artisanal coffee beans", "Home baristas", "Hard to find quality specialty beans locally"),
]


def _always_supported(idea, claims, snippets, allow_local=False):
    return [True] * len(claims)


def _count_cited(*claim_lists):
    total = 0
    cited = 0
    for claims in claim_lists:
        for claim in claims:
            total += 1
            if claim.get("sourceIds"):
                cited += 1
    return cited, total


def _run(idea, target, problem, results, verify_enabled):
    real_verify = {
        "market": market_agent.verify_claims,
        "swot": swot_agent.verify_claims,
        "mvp": mvp_agent.verify_claims,
        "gtm": gtm_agent.verify_claims,
    }
    if not verify_enabled:
        market_agent.verify_claims = _always_supported
        swot_agent.verify_claims = _always_supported
        mvp_agent.verify_claims = _always_supported
        gtm_agent.verify_claims = _always_supported
    # allow_local=True so a rate-limited/exhausted cloud call falls through
    # to the local model instead of raising NeedsDeepAnalysisError - this
    # script measures verification's effect on real output, not the
    # deep-analysis-prompt flow, so every section should still produce
    # something to count.
    market = swot = mvp = gtm = {}
    try:
        market = market_agent.analyze_market_opportunity(idea, target, problem, results, allow_local=True)
        time.sleep(2)  # space out calls against the shared 8000 TPM Groq budget
        swot = swot_agent.analyze_swot(idea, market, None, None, results, allow_local=True)
        time.sleep(2)
        mvp = mvp_agent.analyze_mvp(idea, problem, swot, market, results, allow_local=True)
        time.sleep(2)
        gtm = gtm_agent.analyze_gtm(idea, target, market, None, swot, results, allow_local=True)
    except Exception as exc:
        print(f"    (a section failed even with local fallback: {exc!r} - counting what completed)")
    finally:
        market_agent.verify_claims = real_verify["market"]
        swot_agent.verify_claims = real_verify["swot"]
        mvp_agent.verify_claims = real_verify["mvp"]
        gtm_agent.verify_claims = real_verify["gtm"]

    return _count_cited(
        market.get("trends", []),
        market.get("segments", []),
        swot.get("strengths", []),
        swot.get("weaknesses", []),
        swot.get("opportunities", []),
        swot.get("threats", []),
        swot.get("risks", []),
        mvp.get("features", []),
        gtm.get("channels", []),
    )


def main():
    grand_before_cited = grand_before_total = grand_after_cited = 0
    for idx, (idea, target, problem) in enumerate(IDEAS):
        if idx > 0:
            time.sleep(15)
        print(f"\n=== {idea!r} ===")
        results = retrieval.collect(idea, target, problem)
        print(f"  {len(results)} search results collected (shared across both runs)")

        before_cited, before_total = _run(idea, target, problem, results, verify_enabled=False)
        time.sleep(10)
        after_cited, after_total = _run(idea, target, problem, results, verify_enabled=True)

        stripped = before_cited - after_cited
        pct = (stripped / before_cited * 100) if before_cited else 0
        print(f"  before verification: {before_cited}/{before_total} claims cited")
        print(f"  after verification:  {after_cited}/{after_total} claims cited")
        print(f"  stripped as unsupported: {stripped} ({pct:.0f}% of previously-cited claims)")

        grand_before_cited += before_cited
        grand_before_total += before_total
        grand_after_cited += after_cited

    total_stripped = grand_before_cited - grand_after_cited
    overall_pct = (total_stripped / grand_before_cited * 100) if grand_before_cited else 0
    print(f"\n=== TOTAL across {len(IDEAS)} ideas ===")
    print(f"  {grand_before_cited}/{grand_before_total} claims were cited before verification")
    print(f"  {total_stripped} of those citations ({overall_pct:.0f}%) were stripped as unsupported")


if __name__ == "__main__":
    main()
