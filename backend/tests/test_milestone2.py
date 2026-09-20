import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.graph import confidence_node
from agent.opportunity_score import calculate_opportunity_score
from agent.white_space import analyze_white_space


class Milestone2Tests(unittest.TestCase):
    def test_confidence_counts_angle_agreement(self):
        # agent/confidence.py (a separate, never-wired-in implementation of
        # this same idea) was removed - graph.py's confidence_node is the
        # only one that has ever been reachable from /validate, so it's the
        # one under test here.
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
                "score": 0.4,
            },
            {
                "angle": "Competitors",
                "title": "Top alternatives",
                "snippet": "Several competitors are established.",
                "score": 0.9,
            },
        ]

        confidence = confidence_node({"results": results, "errors": {}})["confidence"]

        self.assertEqual(confidence["perAngle"]["Market size & trends"], {
            "agreeingSources": 1,
            "totalSources": 2,
            "percentage": 50,
            "label": "1/2 sources agree",
        })
        self.assertEqual(confidence["perAngle"]["Competitors"], {
            "agreeingSources": 1,
            "totalSources": 1,
            "percentage": 100,
            "label": "1/1 sources agree",
        })

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
