import os
import unittest

os.environ.setdefault("WEB_CACHE", "0")

from agent import graph, pdf_exporter, sprint_plan

ASSUMPTIONS = {"assumptions": [
    {"assumption": "Freelancers will pay for it", "category": "demand", "uncertainty": "high",
     "howToValidate": "Paid beta with 50 freelancers", "riskIfWrong": "Revenue collapses", "timeToValidate": "1 month"},
    {"assumption": "AI classifies work correctly", "category": "technical", "uncertainty": "high",
     "howToValidate": "Test on 20 real timesheets", "riskIfWrong": "Billing errors", "timeToValidate": "2 weeks"},
    {"assumption": "No rule blocks it", "category": "regulatory", "uncertainty": "low",
     "howToValidate": "Check local rules", "riskIfWrong": "Cannot launch", "timeToValidate": "3 days"},
]}
EXPERIMENTS = [
    {"method": "Smoke test A", "successMetric": "10% sign up"},
    {"method": "Smoke test A", "successMetric": "10% sign up"},
    {"method": "Smoke test B", "successMetric": "5% pre-order"},
]


class SprintTests(unittest.TestCase):
    def test_quickest_high_uncertainty_assumptions_come_first(self):
        sprint = sprint_plan.build_sprint(ASSUMPTIONS, EXPERIMENTS)
        week1 = sprint["weeks"][0]["tasks"]
        self.assertEqual([t["task"] for t in week1], ["Test on 20 real timesheets", "Paid beta with 50 freelancers"])
        self.assertEqual(week1[0]["killsIf"], "Billing errors")

    def test_four_weeks_and_duplicate_experiments_collapse(self):
        sprint = sprint_plan.build_sprint(ASSUMPTIONS, EXPERIMENTS)
        self.assertEqual([w["week"] for w in sprint["weeks"]], [1, 2, 3, 4])
        methods = [t["task"] for t in sprint["weeks"][2]["tasks"]]
        self.assertEqual(methods.count("Smoke test A"), 1)
        self.assertIn("Smoke test B", methods)
        self.assertEqual(sprint["weeks"][2]["tasks"][0]["confirmsIf"], "10% sign up")

    def test_nothing_is_built_without_assumptions(self):
        self.assertIsNone(sprint_plan.build_sprint({"assumptions": []}, EXPERIMENTS))
        self.assertIsNone(sprint_plan.build_interview_script("i", "t", "p", None))


class InterviewScriptTests(unittest.TestCase):
    def test_probes_follow_the_assumption_category_and_carry_checks(self):
        script = sprint_plan.build_interview_script("idea", "Freelancers", "Late payments", ASSUMPTIONS)
        self.assertEqual(len(script["probes"]), 3)
        self.assertIn("cost you each month", next(p for p in script["probes"] if "pay" in p["assumption"])["ask"])
        self.assertEqual(script["probes"][0]["redFlag"], "Billing errors")
        self.assertIn("Late payments", script["opening"][0])
        self.assertTrue(any("pitch" in r for r in script["rules"]))


class NodeAndPdfTests(unittest.TestCase):
    def test_node_adds_both_to_the_action_plan_and_keeps_existing_keys(self):
        state = {"idea": "i", "targetCustomer": "t", "problem": "p", "assumptions": ASSUMPTIONS, "experiments": EXPERIMENTS,
                 "actionPlan": {"next7Days": {"title": "x", "items": []}}}
        out = graph.validation_sprint_node(state)["actionPlan"]
        self.assertIn("sprint", out)
        self.assertIn("interviewScript", out)
        self.assertIn("next7Days", out)

    def test_node_leaves_state_alone_without_an_action_plan_or_after_an_error(self):
        self.assertEqual(graph.validation_sprint_node({"assumptions": ASSUMPTIONS}), {"assumptions": ASSUMPTIONS})
        errored = {"error": "x", "actionPlan": {}}
        self.assertIs(graph.validation_sprint_node(errored), errored)

    def test_pdf_builds_with_sprint_and_script(self):
        plan = {"sprint": sprint_plan.build_sprint(ASSUMPTIONS, EXPERIMENTS),
                "interviewScript": sprint_plan.build_interview_script("i", "t", "p", ASSUMPTIONS)}
        pdf = pdf_exporter.generate_dossier_pdf({"idea": "x", "targetCustomer": "y", "actionPlan": plan})
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
