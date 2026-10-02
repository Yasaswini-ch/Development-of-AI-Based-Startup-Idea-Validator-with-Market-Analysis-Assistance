"""The shared lookup cache: round trips, expiry, fail-open, and that search,
extract, App Store and enrichment lookups really are reused."""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import competitor_agent, tools, web_cache


class CacheCase(unittest.TestCase):
    def setUp(self):
        # Other test modules turn the cache off for the whole process; these
        # tests are the ones that want it on.
        self.env = patch.dict(os.environ, {"WEB_CACHE": "1", "TAVILY_API_KEY": "test-key"})
        self.env.start()
        os.environ.pop("TAVILY_DEEP", None)
        web_cache.clear()

    def tearDown(self):
        web_cache.clear()
        self.env.stop()


class StoreTests(CacheCase):
    def test_a_stored_value_comes_back(self):
        web_cache.put("search", "q", [{"title": "A"}])
        self.assertEqual(web_cache.get("search", "q"), [{"title": "A"}])

    def test_a_miss_returns_none(self):
        self.assertIsNone(web_cache.get("search", "never stored"))

    def test_empty_values_are_not_stored_so_failures_are_retried(self):
        for empty in ([], {}, None, ""):
            web_cache.put("search", "q", empty)
        self.assertIsNone(web_cache.get("search", "q"))

    def test_an_expired_row_is_a_miss(self):
        web_cache.put("app_store", "q", [{"title": "A"}])
        future = time.time() + web_cache.TTL_SECONDS["app_store"] + 5
        with patch("agent.web_cache.time.time", return_value=future):
            self.assertIsNone(web_cache.get("app_store", "q"))

    def test_kinds_do_not_collide(self):
        web_cache.put("search", "same", ["search"])
        web_cache.put("extract", "same", "extract")
        self.assertEqual(web_cache.get("search", "same"), ["search"])
        self.assertEqual(web_cache.get("extract", "same"), "extract")

    def test_writing_removes_expired_rows(self):
        web_cache.put("app_store", "old", [{"title": "Old"}])
        future = time.time() + web_cache.TTL_SECONDS["app_store"] + 5
        with patch("agent.web_cache.time.time", return_value=future):
            web_cache.put("app_store", "new", [{"title": "New"}])
        # the old row is gone from the table, not just ignored
        from sqlalchemy import select

        from agent.db import get_engine, web_cache_table

        with get_engine().begin() as conn:
            keys = [r.cache_key for r in conn.execute(select(web_cache_table)).all()]
        self.assertEqual(len(keys), 1)

    def test_the_off_switch_bypasses_both_reads_and_writes(self):
        with patch.dict(os.environ, {"WEB_CACHE": "0"}):
            web_cache.put("search", "q", ["x"])
            self.assertIsNone(web_cache.get("search", "q"))
        self.assertIsNone(web_cache.get("search", "q"))  # and nothing was written

    def test_a_database_failure_behaves_like_a_miss_and_never_raises(self):
        with patch("agent.web_cache.get_engine", side_effect=RuntimeError("db down")):
            self.assertIsNone(web_cache.get("search", "q"))
            web_cache.put("search", "q", ["x"])  # must not raise


class SearchReuseTests(CacheCase):
    @patch("agent.tools.TavilyClient")
    def test_the_same_query_is_paid_for_once(self, client_cls):
        client_cls.return_value.search.return_value = {
            "results": [{"title": "T", "content": "c", "url": "https://a.example", "score": 0.9}]
        }
        first = tools._from_tavily("freelancer invoicing alternatives", 8)
        second = tools._from_tavily("freelancer invoicing alternatives", 8)
        self.assertEqual(first, second)
        self.assertEqual(client_cls.return_value.search.call_count, 1)

    @patch("agent.tools.TavilyClient")
    def test_deep_and_basic_results_are_cached_separately(self, client_cls):
        client_cls.return_value.search.return_value = {"results": [{"title": "T", "content": "c", "url": "https://a.example", "score": 0.9}]}
        tools._from_tavily("q", 5)
        tools._from_tavily("q", 5, deep=True)
        self.assertEqual(client_cls.return_value.search.call_count, 2)

    @patch("agent.tools.TavilyClient")
    def test_an_empty_result_is_retried_not_remembered(self, client_cls):
        client_cls.return_value.search.return_value = {"results": []}
        tools._from_tavily("q", 5)
        tools._from_tavily("q", 5)
        self.assertEqual(client_cls.return_value.search.call_count, 2)


class ExtractReuseTests(CacheCase):
    @patch("agent.tools.TavilyClient")
    def test_only_pages_not_seen_before_go_to_tavily(self, client_cls):
        extract = client_cls.return_value.extract
        extract.return_value = {
            "results": [
                {"url": "https://a.example", "raw_content": "text a"},
                {"url": "https://b.example", "raw_content": "text b"},
            ]
        }
        tools.extract_full_text(["https://a.example", "https://b.example"])
        extract.return_value = {"results": [{"url": "https://c.example", "raw_content": "text c"}]}
        texts = tools.extract_full_text(["https://a.example", "https://b.example", "https://c.example"])

        self.assertEqual(texts, {"https://a.example": "text a", "https://b.example": "text b", "https://c.example": "text c"})
        self.assertEqual(extract.call_count, 2)
        self.assertEqual(extract.call_args.kwargs["urls"], ["https://c.example"])

    @patch("agent.tools.TavilyClient")
    def test_everything_cached_means_no_call_at_all(self, client_cls):
        client_cls.return_value.extract.return_value = {"results": [{"url": "https://a.example", "raw_content": "text a"}]}
        tools.extract_full_text(["https://a.example"])
        client_cls.reset_mock()
        self.assertEqual(tools.extract_full_text(["https://a.example"]), {"https://a.example": "text a"})
        client_cls.return_value.extract.assert_not_called()


class AppStoreReuseTests(CacheCase):
    @patch("agent.tools._get_json")
    def test_the_same_app_store_query_is_fetched_once(self, get_json):
        get_json.return_value = {
            "results": [{"trackName": "Harvest", "trackViewUrl": "https://apps.apple.com/a/id1", "description": "Track time and invoices"}]
        }
        tools.fetch_app_store_results("track time invoices")
        tools.fetch_app_store_results("track time invoices")
        self.assertEqual(get_json.call_count, 1)


class EnrichmentReuseTests(CacheCase):
    def test_a_known_company_is_looked_up_once_across_runs(self):
        found = {"source": "itunes", "averageRating": 4.6, "ratingCount": 1000}
        with patch.object(competitor_agent, "_producthunt_lookup", return_value=None) as ph, patch.object(
            competitor_agent, "_itunes_lookup", return_value=found
        ) as itunes, patch.object(competitor_agent, "_wikidata_lookup", return_value=None):
            first = [{"name": "Harvest"}]
            competitor_agent._enrich_with_apis(first)
            second = [{"name": "harvest "}]  # a different idea, same company, different spelling
            competitor_agent._enrich_with_apis(second)
        self.assertEqual(first[0]["enrichment"], found)
        self.assertEqual(second[0]["enrichment"], found)
        self.assertEqual(itunes.call_count, 1)
        self.assertEqual(ph.call_count, 1)

    def test_a_company_with_no_match_is_looked_up_again_next_time(self):
        with patch.object(competitor_agent, "_producthunt_lookup", return_value=None), patch.object(
            competitor_agent, "_itunes_lookup", return_value=None
        ) as itunes, patch.object(competitor_agent, "_wikidata_lookup", return_value=None):
            competitor_agent._enrich_with_apis([{"name": "Obscurename"}])
            competitor_agent._enrich_with_apis([{"name": "Obscurename"}])
        self.assertEqual(itunes.call_count, 2)  # failure or no match is not remembered


if __name__ == "__main__":
    unittest.main()
