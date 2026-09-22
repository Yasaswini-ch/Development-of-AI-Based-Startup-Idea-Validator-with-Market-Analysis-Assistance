"""Tests for Track G.1 - Advisor Decision History
(docs/unique-features-plan.md §5.6): agent/decision_history.py's pivot
detection, session_store.py's append_turn wiring it in, and chat_graph.py
threading the summary into the advisor's prompt.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from agent.chat_graph import respond_node, run_chat_turn
from agent.decision_history import append_decision, extract_decision, summarize_decisions
from agent.session_store import append_turn, create_session, get_session
from agent.session_store import clear_sessions


class ExtractDecisionTests(unittest.TestCase):
    def test_returns_none_for_an_ordinary_question(self):
        self.assertIsNone(extract_decision("What's the average CAC for this kind of app?"))

    def test_returns_none_for_an_empty_message(self):
        self.assertIsNone(extract_decision("   "))

    def test_detects_a_pivot_phrase(self):
        self.assertIsNotNone(extract_decision("Let's pivot to enterprise customers instead."))

    def test_detects_instead_of_phrasing(self):
        self.assertIsNotNone(extract_decision("Instead of B2C, we're going after B2B."))

    def test_detects_what_if_we_phrasing(self):
        self.assertIsNotNone(extract_decision("What if we targeted freelancers first?"))

    def test_detects_decided_to_phrasing(self):
        self.assertIsNotNone(extract_decision("We decided to drop the marketplace model."))

    def test_truncates_a_very_long_decision_message(self):
        long_message = "Let's pivot to " + ("enterprise " * 100)
        result = extract_decision(long_message)
        self.assertLessEqual(len(result), 200)


class AppendDecisionTests(unittest.TestCase):
    def test_appends_a_detected_decision(self):
        result = append_decision([], "Let's pivot to a subscription model.", 100.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["at"], 100.0)

    def test_leaves_the_list_unchanged_for_a_non_decision_message(self):
        result = append_decision([{"text": "existing", "at": 1.0}], "What's our TAM?", 200.0)
        self.assertEqual(len(result), 1)

    def test_does_not_mutate_the_original_list(self):
        original = []
        append_decision(original, "Let's pivot to enterprise.", 1.0)
        self.assertEqual(original, [])

    def test_caps_stored_decisions_at_the_max(self):
        decisions = [{"text": f"decision {i}", "at": float(i)} for i in range(20)]
        result = append_decision(decisions, "Let's pivot to yet another idea.", 999.0)
        self.assertLessEqual(len(result), 20)
        self.assertEqual(result[-1]["at"], 999.0)


class SummarizeDecisionsTests(unittest.TestCase):
    def test_empty_list_reads_as_none_recorded(self):
        self.assertEqual(summarize_decisions([]), "None recorded yet.")

    def test_formats_each_decision_as_a_bullet(self):
        summary = summarize_decisions([{"text": "Pivoted to enterprise", "at": 1.0}])
        self.assertIn("- Pivoted to enterprise", summary)


class AppendTurnRecordsDecisionsTests(unittest.TestCase):
    def setUp(self):
        clear_sessions()

    def test_a_pivot_message_is_recorded_in_the_sessions_decisions(self):
        session_id = create_session({"idea": "Idea"})
        append_turn(session_id, "Let's pivot to targeting enterprise buyers.", "Noted.")
        session = get_session(session_id)
        self.assertEqual(len(session["decisions"]), 1)
        self.assertIn("pivot", session["decisions"][0]["text"].lower())

    def test_an_ordinary_message_does_not_add_a_decision(self):
        session_id = create_session({"idea": "Idea"})
        append_turn(session_id, "What's a realistic price point?", "Around $10-20/mo.")
        session = get_session(session_id)
        self.assertEqual(session["decisions"], [])

    def test_a_new_session_starts_with_no_decisions(self):
        session_id = create_session({"idea": "Idea"})
        self.assertEqual(get_session(session_id)["decisions"], [])


class RespondNodeUsesDecisionsTests(unittest.TestCase):
    """respond_node must thread the decisions summary into the prompt
    without requiring the caller to have recorded any - the default (no
    decisions yet) must not error.
    """

    @patch("agent.chat_graph.kickoff_with_fallback")
    def test_respond_node_passes_decisions_summary_into_the_crew_builder(self, kickoff):
        kickoff.return_value.raw = "An answer."
        respond_node(
            {
                "message": "What should I test first?",
                "context": {"idea": "Idea"},
                "history": [],
                "decisions": [{"text": "Pivoted to enterprise", "at": 1.0}],
                "freshResults": [],
            }
        )
        crew_builder = kickoff.call_args[0][0]
        # Actually build the crew to confirm the decisions text reached the
        # task description, rather than just trusting the call didn't error.
        crew = crew_builder("gemini/gemini-3.6-flash")
        self.assertIn("Pivoted to enterprise", crew.tasks[0].description)

    @patch("agent.chat_graph.kickoff_with_fallback")
    def test_respond_node_handles_no_recorded_decisions_yet(self, kickoff):
        kickoff.return_value.raw = "An answer."
        respond_node(
            {
                "message": "What should I test first?",
                "context": {"idea": "Idea"},
                "history": [],
                "freshResults": [],
            }
        )
        crew_builder = kickoff.call_args[0][0]
        crew = crew_builder("gemini/gemini-3.6-flash")
        self.assertIn("None recorded yet.", crew.tasks[0].description)


class RunChatTurnEndToEndTests(unittest.TestCase):
    def setUp(self):
        clear_sessions()

    def test_a_pivot_recorded_in_one_turn_is_available_to_the_next(self):
        session_id = create_session({"idea": "Idea"})

        with patch("agent.chat_graph.chat_turn.invoke", return_value={"reply": "Got it."}) as invoke:
            run_chat_turn(session_id, "Let's pivot to targeting enterprise buyers.")
            run_chat_turn(session_id, "What should we validate first?")

        # The second turn's invocation should have received the decision
        # recorded by the first turn - decisions are read from the session
        # at the start of run_chat_turn, after the previous append_turn.
        second_call_state = invoke.call_args_list[1][0][0]
        self.assertEqual(len(second_call_state["decisions"]), 1)


if __name__ == "__main__":
    unittest.main()
