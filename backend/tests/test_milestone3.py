import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import asyncio

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import main
from agent import retrieval
from agent.chat_graph import interpret_node, run_chat_turn
from agent.chat_graph import ChatRateLimitError
from agent.graph import gtm_node, mvp_node, swot_node
from agent.graph import pipeline
from agent.gtm_agent import analyze_gtm
from agent.mvp_agent import analyze_mvp
from agent.session_store import clear_sessions, create_session, get_session
from agent.structured_output import extract_json_object
from agent.swot_agent import analyze_swot


class MilestoneThreeTests(unittest.TestCase):
    def setUp(self):
        clear_sessions()
        main._cache.clear()

    def test_structured_parser_ignores_braces_inside_strings(self):
        value = extract_json_object(
            'scratch {"value":"a {quoted} value"} done',
            lambda item: isinstance(item.get("value"), str),
        )
        self.assertEqual(value, {"value": "a {quoted} value"})

    @patch("agent.swot_agent.kickoff_with_fallback")
    def test_swot_contract(self, kickoff):
        kickoff.return_value = SimpleNamespace(
            raw=(
                '{"strengths":["Focused niche"],"weaknesses":["Limited proof"],'
                '"opportunities":["Growing demand"],"threats":["Established rivals"],'
                '"risks":[{"risk":"Low adoption","severity":"high","likelihood":"medium"}]}'
            )
        )
        result = analyze_swot("Idea", {}, {}, {}, [])
        self.assertEqual(result["risks"][0]["severity"], "high")

    @patch("agent.mvp_agent.kickoff_with_fallback")
    @patch("agent.gtm_agent.kickoff_with_fallback")
    def test_mvp_and_gtm_contracts(self, gtm_kickoff, mvp_kickoff):
        mvp_kickoff.return_value = SimpleNamespace(
            raw=(
                '{"features":[{"feature":"Landing page","rationale":"Test demand",'
                '"impact":"high","effort":"low"}]}'
            )
        )
        gtm_kickoff.return_value = SimpleNamespace(
            raw=(
                '{"positioning":"Fast evidence for founders","channels":["Founder communities"],'
                '"earlyCustomerApproach":"Recruit ten design partners."}'
            )
        )
        self.assertEqual(analyze_mvp("Idea", "Problem", {}, {})["features"][0]["impact"], "high")
        self.assertEqual(analyze_gtm("Idea", "Founders", {}, {}, {})["channels"], ["Founder communities"])

    def test_strategy_node_failures_are_isolated(self):
        base = {"idea": "Idea", "results": [], "errors": {}}
        for target, node, key in (
            ("agent.graph.analyze_swot", swot_node, "swot"),
            ("agent.graph.analyze_mvp", mvp_node, "mvp"),
            ("agent.graph.analyze_gtm", gtm_node, "gtm"),
        ):
            with self.subTest(node=key), patch(target, side_effect=RuntimeError("failed")):
                result = node(base)
                self.assertIsNone(result[key])
                self.assertIn(key, result["errors"])
                self.assertNotIn("error", result)

    def test_session_and_chat_history(self):
        session_id = create_session({"idea": "Idea"})
        with patch(
            "agent.chat_graph.chat_turn.invoke",
            return_value={"reply": "Validate willingness to pay."},
        ):
            reply = run_chat_turn(session_id, "What should I test?")
        self.assertEqual(reply, "Validate willingness to pay.")
        self.assertEqual(len(get_session(session_id)["history"]), 1)

    def test_chat_enforces_message_and_rate_limits(self):
        session_id = create_session({"idea": "Idea"})
        with self.assertRaises(ValueError):
            run_chat_turn(session_id, "x" * 1201)

        with patch(
            "agent.chat_graph.chat_turn.invoke",
            return_value={"reply": "Answer"},
        ):
            for _ in range(6):
                run_chat_turn(session_id, "Question")
            with self.assertRaises(ChatRateLimitError):
                run_chat_turn(session_id, "One too many")

    def test_chat_search_intent_and_scoped_retrieval(self):
        interpreted = interpret_node(
            {"message": "Find the latest competitor pricing", "context": {"idea": "Idea"}}
        )
        self.assertTrue(interpreted["needsSearch"])

        with patch(
            "agent.retrieval.fetch_results",
            return_value=[
                {"title": "One", "url": "https://example.com/one", "score": 0.8},
                {"title": "Duplicate", "url": "https://example.com/one", "score": 0.4},
            ],
        ) as fetch:
            results = retrieval.collect_scoped("latest pricing")
        fetch.assert_called_once_with("latest pricing", max_results=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["angle"], "Follow-up research")

    def test_search_angles_use_compact_product_subject(self):
        angles = retrieval.build_search_angles(
            "An AI-powered meal planning app that creates affordable weekly plans for households",
            "Budget-conscious working families in urban India",
            "Families waste ingredients and exceed their grocery budget",
        )
        # Subject must stay short and drop the "ai-powered" filler adjective,
        # but - unlike the old exact-string assertion here - it must now
        # also carry a distinctive noun from *after* "that" (e.g.
        # "households"/"plans"), not just the generic "meal planning app"
        # prefix. Losing everything after "that" was the actual live bug:
        # for pitches phrased as "[generic type] that [does the specific
        # thing]" it discarded every differentiating word, so Market/
        # Competitors/Industry-news queries searched for something fully
        # generic and surfaced unrelated results.
        market_query = angles[0][1][0]
        self.assertTrue(market_query.startswith("meal"))
        self.assertNotIn("ai-powered", market_query)
        self.assertTrue(
            any(word in market_query for word in ("households", "plans")),
            f"expected a distinctive noun from after 'that' in {market_query!r}",
        )
        self.assertTrue(all(len(query) < 150 for _, queries in angles for query in queries))


    @patch("main.pipeline.invoke")
    def test_validate_returns_session_and_milestone_outputs(self, invoke):
        invoke.return_value = {
            "summary": "Summary",
            "results": [{"title": "Source"}],
            "swot": {"strengths": []},
            "mvp": {"features": []},
            "gtm": {"positioning": "Position"},
            "errors": {},
        }
        response = asyncio.run(main.validate_idea(main.ValidateRequest(idea="Idea")))
        self.assertIn("sessionId", response)
        self.assertEqual(response["gtm"]["positioning"], "Position")

    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_full_pipeline_reaches_all_milestone_nodes(
        self,
        collect,
        market,
        competitors,
        swot,
        mvp,
        gtm,
    ):
        collect.return_value = [
            {
                "title": "Demand grows",
                "snippet": "Demand is growing.",
                "url": "https://example.com",
                "angle": "Market size & trends",
                "score": 0.8,
            }
        ]
        market.return_value = {
            "marketSize": "Growing niche",
            "trends": ["Growing demand"],
            "segments": [
                {
                    "segment": "Founders",
                    "painPoints": "Uncertain demand",
                    "motivations": "Reduce risk",
                    "buyingBehavior": "Research online",
                }
            ],
            "opportunityScore": 0,
        }
        competitors.return_value = {"competitors": []}
        swot.return_value = {
            "strengths": ["Focused"],
            "weaknesses": ["Early"],
            "opportunities": ["Demand"],
            "threats": ["Rivals"],
            "risks": [],
        }
        mvp.return_value = {"features": []}
        gtm.return_value = {
            "positioning": "Evidence first",
            "channels": ["Communities"],
            "earlyCustomerApproach": "Design partners",
        }

        result = pipeline.invoke({"idea": "Idea", "targetCustomer": "Founders", "problem": "Risk"})

        self.assertEqual(result["swot"]["strengths"], ["Focused"])
        self.assertEqual(result["gtm"]["channels"], ["Communities"])
        self.assertIn("whiteSpace", result)


if __name__ == "__main__":
    unittest.main()
