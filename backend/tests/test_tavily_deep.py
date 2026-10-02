"""Tavily deep content: advanced search for two angles, full-page Extract for a
few competitor sources, safe fallbacks, and an off switch."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("WEB_CACHE", "0")  # tests must never read or write the shared lookup cache (agent/web_cache.py)
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import main
from agent import retrieval, tools


def _tavily_response(*urls):
    return {"results": [{"title": f"T {u}", "content": "text", "url": u, "score": 0.9} for u in urls]}


class DeepSearchTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
        self.env.start()
        os.environ.pop("TAVILY_DEEP", None)

    def tearDown(self):
        self.env.stop()

    @patch("agent.tools.TavilyClient")
    def test_deep_search_asks_for_advanced_depth_and_several_chunks(self, client_cls):
        client_cls.return_value.search.return_value = _tavily_response("https://a.example")
        tools._from_tavily("q", 5, deep=True)
        kwargs = client_cls.return_value.search.call_args.kwargs
        self.assertEqual(kwargs["search_depth"], "advanced")
        self.assertEqual(kwargs["chunks_per_source"], 3)

    @patch("agent.tools.TavilyClient")
    def test_plain_search_stays_basic(self, client_cls):
        client_cls.return_value.search.return_value = _tavily_response("https://a.example")
        tools._from_tavily("q", 5)
        self.assertNotIn("search_depth", client_cls.return_value.search.call_args.kwargs)

    @patch("agent.tools.TavilyClient")
    def test_a_failed_advanced_search_retries_with_basic(self, client_cls):
        search = client_cls.return_value.search
        search.side_effect = [RuntimeError("credits exhausted"), _tavily_response("https://a.example")]
        results = tools._from_tavily("q", 5, deep=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(search.call_count, 2)
        self.assertNotIn("search_depth", search.call_args_list[1].kwargs)

    @patch("agent.tools.TavilyClient")
    def test_the_off_switch_disables_deep_search_and_extract(self, client_cls):
        client_cls.return_value.search.return_value = _tavily_response("https://a.example")
        with patch.dict(os.environ, {"TAVILY_DEEP": "0"}):
            tools._from_tavily("q", 5, deep=True)
            texts = tools.extract_full_text(["https://a.example"])
        self.assertNotIn("search_depth", client_cls.return_value.search.call_args.kwargs)
        self.assertEqual(texts, {})
        client_cls.return_value.extract.assert_not_called()


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
        self.env.start()
        os.environ.pop("TAVILY_DEEP", None)

    def tearDown(self):
        self.env.stop()

    @patch("agent.tools.TavilyClient")
    def test_returns_capped_text_per_url_and_skips_empty_pages(self, client_cls):
        client_cls.return_value.extract.return_value = {
            "results": [
                {"url": "https://a.example", "raw_content": "x" * 9000},
                {"url": "https://b.example", "raw_content": "   "},
            ]
        }
        texts = tools.extract_full_text(["https://a.example", "https://b.example"], max_chars=100)
        self.assertEqual(list(texts), ["https://a.example"])
        self.assertEqual(len(texts["https://a.example"]), 100)

    @patch("agent.tools.TavilyClient")
    def test_a_failure_returns_nothing_instead_of_raising(self, client_cls):
        client_cls.return_value.extract.side_effect = RuntimeError("boom")
        self.assertEqual(tools.extract_full_text(["https://a.example"]), {})

    def test_no_key_or_no_urls_never_calls_tavily(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}), patch("agent.tools.TavilyClient") as client_cls:
            self.assertEqual(tools.extract_full_text(["https://a.example"]), {})
            client_cls.assert_not_called()
        with patch("agent.tools.TavilyClient") as client_cls:
            self.assertEqual(tools.extract_full_text([]), {})
            client_cls.assert_not_called()


class CollectTests(unittest.TestCase):
    def _hit(self, url):
        return {"title": "T", "snippet": "s", "url": url, "score": 0.8}

    def test_only_the_two_deep_angles_ask_for_deep_search(self):
        calls = []

        def fake_fetch(query, max_results=5, deep=False):
            calls.append(deep)
            return [self._hit(f"https://x.example/{len(calls)}")]

        with patch("agent.retrieval.fetch_results", side_effect=fake_fetch), patch(
            "agent.retrieval.extract_full_text", return_value={}
        ):
            retrieval.collect("A scheduling app", "Dentists", "No-shows")
        self.assertIn(True, calls)
        self.assertIn(False, calls)

    def test_only_the_top_three_competitor_results_get_full_text(self):
        results = [
            {"angle": "Competitors", "url": f"https://c.example/{i}", "score": 1 - i / 10} for i in range(5)
        ] + [{"angle": "Industry news", "url": "https://n.example", "score": 0.99}]
        with patch("agent.retrieval.extract_full_text", return_value={r["url"]: "FULL " + r["url"] for r in results}) as extract:
            retrieval._attach_full_text(results)
        asked = extract.call_args.args[0]
        self.assertEqual(asked, [f"https://c.example/{i}" for i in range(3)])
        self.assertEqual([("fullText" in r) for r in results], [True, True, True, False, False, False])

    def test_a_result_with_no_extracted_text_is_left_unchanged(self):
        results = [{"angle": "Competitors", "url": "https://c.example/0", "score": 0.9}]
        with patch("agent.retrieval.extract_full_text", return_value={}):
            retrieval._attach_full_text(results)
        self.assertNotIn("fullText", results[0])


class AppStoreLayerTests(unittest.TestCase):
    def _app(self, name, description="A time tracking and invoicing app for freelancers"):
        return {"trackName": name, "trackViewUrl": f"https://apps.apple.com/us/app/{name}/id1?mt=8", "description": description}

    @patch("agent.tools._get_json")
    def test_relevant_apps_become_ordinary_search_results(self, get_json):
        get_json.return_value = {"results": [self._app("Harvest")]}
        hits = tools.fetch_app_store_results("track time invoices freelancers")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Harvest")
        self.assertEqual(hits[0]["url"], "https://apps.apple.com/us/app/Harvest/id1")  # query string dropped
        self.assertEqual(hits[0]["provider"], "app_store")
        self.assertTrue(hits[0]["snippet"].startswith("Harvest."))

    @patch("agent.tools._get_json")
    def test_apps_keep_apples_ranking_order(self, get_json):
        get_json.return_value = {"results": [self._app("First"), self._app("Second"), self._app("Third")]}
        hits = tools.fetch_app_store_results("track time invoices freelancers")
        self.assertEqual([h["title"] for h in hits], ["First", "Second", "Third"])
        self.assertGreater(hits[0]["score"], hits[1]["score"])

    @patch("agent.tools._get_json", side_effect=OSError("offline"))
    def test_a_failure_returns_nothing_instead_of_raising(self, _):
        self.assertEqual(tools.fetch_app_store_results("track time invoices freelancers"), [])

    @patch("agent.tools._get_json")
    def test_the_off_switch_skips_the_request(self, get_json):
        with patch.dict(os.environ, {"ITUNES_DISCOVERY": "0"}):
            self.assertEqual(tools.fetch_app_store_results("track time invoices freelancers"), [])
        get_json.assert_not_called()

    def _store_app(self, name, snippet, rank):
        return {
            "title": name,
            "snippet": snippet,
            "url": f"https://apps.apple.com/us/app/{name}/id{rank}",
            "score": 0.8 - rank / 50,
            "provider": "app_store",
        }

    def test_collect_adds_only_apps_that_share_topic_words_with_the_idea(self):
        apps = [
            self._store_app("Harvest", "Track time and invoices for freelancers", 1),
            self._store_app("Pony Game", "Ride colourful ponies through a magic forest", 2),
        ]
        with patch("agent.retrieval.fetch_results", return_value=[]), patch(
            "agent.retrieval.fetch_app_store_results", return_value=apps
        ), patch("agent.retrieval.extract_full_text", return_value={}):
            results = retrieval.collect(
                "An app that helps freelancers track time and send invoices", "Small agencies", "Slow billing"
            )
        found = [r for r in results if r.get("provider") == "app_store"]
        self.assertEqual([r["title"] for r in found], ["Harvest"])
        self.assertEqual(found[0]["angle"], "Competitors")

    def test_at_most_five_apps_are_added(self):
        apps = [self._store_app(f"Invoice Time Tracker {i}", "Track time and invoices for freelancers", i) for i in range(9)]
        with patch("agent.retrieval.fetch_results", return_value=[]), patch(
            "agent.retrieval.fetch_app_store_results", return_value=apps
        ), patch("agent.retrieval.extract_full_text", return_value={}):
            results = retrieval.collect(
                "An app that helps freelancers track time and send invoices", "Small agencies", "Slow billing"
            )
        self.assertEqual(len([r for r in results if r.get("provider") == "app_store"]), 5)


class ResponseTests(unittest.TestCase):
    @patch("agent.graph.analyze_revenue_models")
    @patch("agent.graph.analyze_assumptions")
    @patch("agent.graph.analyze_gtm")
    @patch("agent.graph.analyze_mvp")
    @patch("agent.graph.analyze_swot")
    @patch("agent.graph.analyze_competitors")
    @patch("agent.graph.analyze_market_opportunity")
    @patch("agent.graph.retrieval.collect")
    def test_full_text_never_reaches_the_api_response(self, collect, market, competitors, swot, mvp, gtm, assumptions, revenue):
        collect.return_value = [
            {"title": "S", "snippet": "short", "url": "https://example.com", "angle": "Competitors", "score": 0.6, "fullText": "LONG " * 400}
        ]
        market.return_value = {"marketSize": "x", "trends": [], "segments": [], "opportunityScore": 0}
        competitors.return_value = {"competitors": []}
        swot.return_value = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": [], "risks": []}
        mvp.return_value = {"features": []}
        gtm.return_value = {"positioning": "P", "channels": [], "earlyCustomerApproach": "E"}
        assumptions.return_value = {"assumptions": []}
        revenue.return_value = {"models": []}

        body = TestClient(main.app).post("/validate", json={"idea": "Fulltext stripping idea"}).json()
        self.assertEqual(len(body["results"]), 1)
        self.assertNotIn("fullText", body["results"][0])
        self.assertEqual(body["results"][0]["snippet"], "short")


if __name__ == "__main__":
    unittest.main()
