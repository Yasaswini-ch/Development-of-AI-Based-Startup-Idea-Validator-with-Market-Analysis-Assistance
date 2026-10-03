import os
import unittest

os.environ.setdefault("WEB_CACHE", "0")

from agent import graph, trace


class TraceRegistryTests(unittest.TestCase):
    def test_run_key_ignores_case_and_spacing(self):
        self.assertEqual(trace.run_key("An  Idea", "Founders", "Slow"), trace.run_key("an idea", "founders ", "slow"))
        self.assertNotEqual(trace.run_key("a", "b", "c"), trace.run_key("a", "b", "d"))

    def test_steps_are_taken_once_in_order(self):
        key = trace.run_key("take-test", "t", "p")
        trace.record(key, "web_search", 1.234, [])
        trace.record(key, "swot_analysis", 2.0, ["m1"])
        steps = trace.take(key)
        self.assertEqual([s["node"] for s in steps], ["web_search", "swot_analysis"])
        self.assertEqual(steps[0]["seconds"], 1.23)
        self.assertEqual(trace.take(key), [])

    def test_models_noted_inside_a_step_are_collected_without_duplicates(self):
        token, step = trace.begin_step()
        trace.note_model("groq/a")
        trace.note_model("groq/a")
        trace.note_model("gemini/b")
        trace.end_step(token)
        self.assertEqual(step["models"], ["groq/a", "gemini/b"])
        trace.note_model("ignored")  # outside any step: must not raise

    def test_timed_wrapper_records_the_step_with_its_model(self):
        def node(state):
            trace.note_model("groq/x")
            return state

        state = {"idea": "wrapper-test", "targetCustomer": "t", "problem": "p"}
        graph._timed("fake_node", node)(state)
        steps = trace.take(trace.run_key("wrapper-test", "t", "p"))
        self.assertEqual(steps[0]["node"], "fake_node")
        self.assertEqual(steps[0]["models"], ["groq/x"])


if __name__ == "__main__":
    unittest.main()
