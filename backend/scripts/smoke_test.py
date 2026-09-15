"""Fast local smoke test for Milestone 2 helper logic.

Run from the repository root:

    python backend/scripts/smoke_test.py
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.confidence import calculate_confidence
from agent.opportunity_score import calculate_opportunity_score
from agent.white_space import analyze_white_space


def main() -> None:
    results = [
        {
            "angle": "Market size & trends",
            "title": "AI validation market growth",
            "snippet": "The market is growing with rising adoption among founders.",
            "score": 0.8,
        },
        {
            "angle": "Competitors",
            "title": "Existing alternatives",
            "snippet": "Competitors and alternatives are emerging in the market.",
            "score": 0.7,
        },
    ]
    market = {
        "marketSize": "The global market is growing quickly.",
        "trends": ["Rising adoption", "Growing demand"],
        "segments": [
            {
                "segment": "Student founders",
                "painPoints": "They need quick validation before building.",
                "motivations": "They want evidence-backed project direction.",
            }
        ],
    }
    competitors = {"competitors": [{"name": "ExampleCo"}]}

    confidence = calculate_confidence(results)
    score = calculate_opportunity_score(market, competitors, results)
    white_space = analyze_white_space(market, competitors, results)

    assert confidence["marketGrowth"]["total"] == 1
    assert score > 0
    assert white_space["opportunities"]
    print("Milestone 2 smoke test passed.")


if __name__ == "__main__":
    main()
