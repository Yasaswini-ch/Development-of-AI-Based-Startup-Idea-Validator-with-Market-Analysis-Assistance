"""Tests for agent/user_analytics.py's aggregation and GET /me/analytics."""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete

import main
from agent.auth import signup
from agent.db import get_engine, users_table
from agent.session_store import clear_sessions, create_session
from agent.user_analytics import get_user_analytics


def _clear_users():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(users_table))


def _context(
    idea,
    score=None,
    uncertainty_high=0,
    errors=None,
    confidence_pct=None,
    viability=None,
    revenue_models=None,
    risk_text=None,
    competitors=None,
    action_plan=None,
    target_customer=None,
    problem=None,
):
    return {
        "idea": idea,
        "targetCustomer": target_customer,
        "problem": problem,
        "marketOpportunity": {"opportunityScore": score, "marketSize": "Growing"} if score is not None else {},
        "assumptions": {
            "assumptions": [{"category": "demand", "uncertainty": "high"} for _ in range(uncertainty_high)]
        },
        "errors": errors or {},
        "confidence": {"percentage": confidence_pct} if confidence_pct is not None else {},
        "marketViability": viability,
        "revenueModels": {"models": revenue_models} if revenue_models else None,
        "competitors": {"competitors": competitors} if competitors is not None else None,
        "actionPlan": action_plan,
        "swot": {"strengths": [], "risks": [{"risk": risk_text}] if risk_text else []},
    }


class UserAnalyticsAggregationTests(unittest.TestCase):
    def setUp(self):
        clear_sessions()

    def test_no_sessions_does_not_crash(self):
        result = get_user_analytics("nonexistent-user")
        self.assertEqual(result["ideasValidated"], 0)
        self.assertIsNone(result["kpis"]["avgOpportunityScore"])
        self.assertEqual(result["ideas"], [])

    def test_kpis_from_multiple_sessions(self):
        user_id = "user-1"
        create_session(_context("Idea A", score=80, uncertainty_high=2, confidence_pct=90), user_id=user_id)
        create_session(_context("Idea B", score=60, uncertainty_high=1, errors={"swot": "failed"}, confidence_pct=70), user_id=user_id)

        result = get_user_analytics(user_id)
        self.assertEqual(result["ideasValidated"], 2)
        self.assertEqual(result["kpis"]["avgOpportunityScore"], 70)
        self.assertEqual(result["kpis"]["bestScore"], 80)
        self.assertEqual(result["kpis"]["bestScoreIdea"], "Idea A")
        self.assertEqual(result["kpis"]["highRiskAssumptions"], 3)
        self.assertEqual(result["kpis"]["completeRuns"], 1)
        self.assertEqual(result["kpis"]["degradedRuns"], 1)
        self.assertEqual(result["kpis"]["avgSourceAgreement"], 80)

    def test_viability_dimensions_averaged_across_ideas_that_have_it(self):
        user_id = "user-2"
        create_session(
            _context("Idea A", score=50, viability={"marketDemand": 80, "executionRisk": 20, "growthVelocity": 60, "competitionClarity": 100, "timing": 40}),
            user_id=user_id,
        )
        create_session(_context("Idea B", score=50, viability=None), user_id=user_id)

        result = get_user_analytics(user_id)
        self.assertEqual(result["viabilityDimensions"]["marketDemand"], 80)
        self.assertEqual(result["viabilityDimensions"]["timing"], 40)

    def test_revenue_model_distribution_buckets_free_text_names(self):
        user_id = "user-3"
        create_session(
            _context("Idea A", score=50, revenue_models=[{"name": "Monthly SaaS Subscription"}, {"name": "Usage-based licensing"}]),
            user_id=user_id,
        )
        result = get_user_analytics(user_id)
        buckets = {row["model"]: row["count"] for row in result["revenueModelDistribution"]}
        self.assertEqual(buckets["Subscription / SaaS"], 1)
        self.assertEqual(buckets["Usage-based"], 1)

    def test_assumption_risk_by_category(self):
        user_id = "user-4"
        create_session(_context("Idea A", score=50, uncertainty_high=2), user_id=user_id)
        result = get_user_analytics(user_id)
        self.assertEqual(result["assumptionRiskByCategory"]["demand"]["high"], 2)

    def test_swot_theme_cloud_counts_recurring_text(self):
        user_id = "user-5"
        create_session(_context("Idea A", score=50, risk_text="Thin margins"), user_id=user_id)
        create_session(_context("Idea B", score=50, risk_text="Thin margins"), user_id=user_id)
        result = get_user_analytics(user_id)
        top_risk = result["swotThemes"]["risks"][0]
        self.assertEqual(top_risk["text"], "Thin margins")
        self.assertEqual(top_risk["count"], 2)

    def test_zero_score_is_not_counted_as_a_real_score(self):
        # opportunityScore of 0 means the score node degraded/failed, not
        # "a venture scored zero" - same rule report_assembler.py and the
        # opportunity_score_node itself already follow.
        user_id = "user-6"
        create_session(_context("Idea A", score=0), user_id=user_id)
        result = get_user_analytics(user_id)
        self.assertIsNone(result["kpis"]["avgOpportunityScore"])
        self.assertEqual(result["ideas"][0]["score"], 0)  # still shown in the table, just not averaged

    def test_recommendation_text_matches_score_tier(self):
        user_id = "user-7"
        create_session(_context("Strong idea", score=80, risk_text="Thin margins"), user_id=user_id)
        create_session(_context("Moderate idea", score=55), user_id=user_id)
        create_session(_context("Weak idea", score=30), user_id=user_id)

        result = get_user_analytics(user_id)
        by_idea = {row["idea"]: row["recommendation"] for row in result["ideas"]}
        self.assertIn("Strong candidate", by_idea["Strong idea"])
        self.assertIn("thin margins", by_idea["Strong idea"])  # risk clause lowercased into the sentence
        self.assertIn("Moderate", by_idea["Moderate idea"])
        self.assertIn("pivoting", by_idea["Weak idea"])

    def test_competition_label_buckets_by_named_competitor_count(self):
        user_id = "user-8"
        create_session(_context("No competitors found", score=50, competitors=[]), user_id=user_id)
        create_session(_context("A couple competitors", score=50, competitors=[{"name": "A"}, {"name": "B"}]), user_id=user_id)
        create_session(_context("Many competitors", score=50, competitors=[{"name": str(i)} for i in range(6)]), user_id=user_id)

        result = get_user_analytics(user_id)
        by_idea = {row["idea"]: row["competitionLabel"] for row in result["ideas"]}
        self.assertEqual(by_idea["No competitors found"], "Unclear")
        self.assertEqual(by_idea["A couple competitors"], "Low")
        self.assertEqual(by_idea["Many competitors"], "High")

    def test_next_steps_flattens_action_plan_windows_in_order(self):
        user_id = "user-9"
        action_plan = {
            "next7Days": {"title": "x", "items": [{"text": "Interview 10 customers"}]},
            "next30Days": {"title": "x", "items": [{"text": "Build a prototype"}]},
            "next90Days": {"title": "x", "items": [{"text": "Launch a pilot"}]},
        }
        create_session(_context("Idea A", score=50, action_plan=action_plan), user_id=user_id)
        result = get_user_analytics(user_id)
        self.assertEqual(
            result["ideas"][0]["nextSteps"],
            ["Interview 10 customers", "Build a prototype", "Launch a pilot"],
        )

    def test_score_trend_carries_confidence_percentage_and_is_chronological(self):
        user_id = "user-10"
        create_session(_context("First", score=60, confidence_pct=70), user_id=user_id)
        create_session(_context("Second", score=80, confidence_pct=90), user_id=user_id)

        result = get_user_analytics(user_id)
        trend = result["scoreTrend"]
        self.assertEqual(len(trend), 2)
        # list_sessions_for_user orders newest-first; the trend must be
        # re-sorted oldest-first for a left-to-right chronological chart.
        self.assertEqual(trend[0]["idea"], "First")
        self.assertEqual(trend[1]["idea"], "Second")
        self.assertEqual(trend[0]["confidencePercentage"], 70)

    def test_a_session_that_disappears_between_listing_and_fetch_does_not_misalign_the_rest(self):
        # Regression: entries and contexts used to be built as two
        # separately-filtered lists and zipped together - a session
        # expiring/pruned between list_sessions_for_user and get_session
        # would drop one context but not its entry, silently shifting
        # every later (entry, context) pairing by one.
        user_id = "user-11"
        create_session(_context("Idea A", score=60), user_id=user_id)
        create_session(_context("Idea B", score=90), user_id=user_id)

        from unittest.mock import patch
        import agent.user_analytics as user_analytics_module

        real_get_session = user_analytics_module.get_session
        entries = list(user_analytics_module.list_sessions_for_user(user_id, limit=100))
        vanished_id = entries[0]["sessionId"]  # newest, per list_sessions_for_user's ordering

        def flaky_get_session(session_id):
            if session_id == vanished_id:
                return None
            return real_get_session(session_id)

        with patch.object(user_analytics_module, "get_session", side_effect=flaky_get_session):
            result = user_analytics_module.get_user_analytics(user_id)

        self.assertEqual(result["ideasValidated"], 1)
        self.assertEqual(len(result["ideas"]), 1)
        remaining_idea = result["ideas"][0]["idea"]
        remaining_score = result["ideas"][0]["score"]
        # Whichever idea survived, its own score must stay attached to it -
        # the bug this guards against would instead attach the vanished
        # idea's neighbor's score to the wrong idea name.
        self.assertEqual(remaining_score, 60 if remaining_idea == "Idea A" else 90)


class MeAnalyticsEndpointTests(unittest.TestCase):
    def setUp(self):
        _clear_users()
        clear_sessions()
        self.client = TestClient(main.app)

    def test_requires_auth(self):
        response = self.client.get("/me/analytics")
        self.assertEqual(response.status_code, 401)

    def test_returns_aggregated_shape_for_signed_in_user(self):
        signup_result = signup("founder@example.com", "correct-horse-battery")
        create_session(_context("Idea A", score=75), user_id=signup_result["user"]["id"])

        response = self.client.get("/me/analytics", headers={"Authorization": f"Bearer {signup_result['token']}"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ideasValidated"], 1)
        self.assertEqual(body["kpis"]["avgOpportunityScore"], 75)


if __name__ == "__main__":
    unittest.main()
