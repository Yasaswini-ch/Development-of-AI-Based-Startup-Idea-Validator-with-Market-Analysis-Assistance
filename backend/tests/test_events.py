"""Tests for agent/events.py - the durable operational event log backing
GET /admin/platform-metrics (see that module's docstring for why this
exists alongside agent/metrics.py's in-process counters).
"""

import sys
import time
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent import events


class EventsTests(unittest.TestCase):
    def setUp(self):
        events.clear()

    def test_record_and_query_round_trip(self):
        events.record("node_latency", node="swot", detail={"seconds": 8.2})
        rows = events.query("node_latency")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["node"], "swot")
        self.assertEqual(rows[0]["detail"], {"seconds": 8.2})

    def test_query_filters_by_type(self):
        events.record("cache_hit")
        events.record("cache_miss")
        self.assertEqual(len(events.query("cache_hit")), 1)
        self.assertEqual(len(events.query("cache_miss")), 1)

    def test_query_filters_by_node(self):
        events.record("node_latency", node="swot", detail={"seconds": 1})
        events.record("node_latency", node="mvp", detail={"seconds": 2})
        rows = events.query("node_latency", node="swot")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["node"], "swot")

    def test_query_respects_since_cutoff(self):
        events.record("model_used", detail={"model": "groq/qwen/qwen3.8-27b"})
        future_cutoff = time.time() + 10
        self.assertEqual(events.query("model_used", since=future_cutoff), [])
        self.assertEqual(len(events.query("model_used", since=time.time() - 10)), 1)

    def test_query_respects_limit_and_orders_newest_first(self):
        for i in range(5):
            events.record("cache_hit", detail={"i": i})
        rows = events.query("cache_hit", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["detail"]["i"], 4)
        self.assertEqual(rows[1]["detail"]["i"], 3)

    def test_record_never_raises_even_if_detail_is_unusual(self):
        try:
            events.record("weird", detail={"nested": {"a": [1, 2, {"b": None}]}})
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"record() must never raise, got {exc!r}")

    def test_clear_empties_the_log(self):
        events.record("cache_hit")
        events.clear()
        self.assertEqual(events.query("cache_hit"), [])


if __name__ == "__main__":
    unittest.main()
