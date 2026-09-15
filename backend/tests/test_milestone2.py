import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.confidence import calculate_confidence
from agent.opportunity_score import calculate_opportunity_score
from agent.white_space import analyze_white_space


class Milestone2Tests(unittest.TestCase):
    def test_confidence_counts_angle_agreement(self):
        results = [
            {
                "angle": "Market size & trends",
                "title": "Market is growing",
                "snippet": "Demand is rising quickly.",
                "score": 0.8,
            },
            {
                "angle": "Market size & trends",
                "title": "Category overview",
                "snippet": "A static overview.",
                "score": 0.7,
            },
            {
                "angle": "Competitors",
                "title": "Top alternatives",
                "snippet": "Several competitors are established.",
                "score": 0.9,
            },
        ]

        confidence = calculate_confidence(results)

        self.assertEqual(confidence["marketGrowth"], {"agree": 1, "total": 2})
        self.assertEqual(confidence["competitivePressure"], {"agree": 1, "total": 1})

    def test_opportunity_score_uses_grounded_market_and_competition_signal(self):
        score = calculate_opportunity_score(
            {
                "marketSize": "The global market is worth billions and growing.",
                "trends": ["Rising adoption", "Demand is growing", "Expanding use cases"],
            },
            {"competitors": [{"name": "One"}, {"name": "Two"}]},
            [],
        )

        self.assertGreaterEqual(score, 80)

    def test_white_space_analysis_uses_segments_and_competitor_density(self):
        white_space = analyze_white_space(
            {
                "segments": [
                    {
                        "segment": "Student founders",
                        "painPoints": "They struggle to validate ideas before building.",
                        "motivations": "They want quick evidence for project decisions.",
                    }
                ]
            },
            {"competitors": []},
            [
                {
                    "angle": "Customer demand",
                    "snippet": "Founders increasingly look for fast validation tools.",
                    "score": 0.9,
                }
            ],
        )

        self.assertIn("No named competitors", white_space["competitionNote"])
        self.assertEqual(white_space["opportunities"][0]["title"], "Serve Student founders")


if __name__ == "__main__":
    unittest.main()
