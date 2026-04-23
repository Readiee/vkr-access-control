"""Unit-тесты AccessExplainer (FIX9): rule-based justifications для SWRL.

is_available_for и satisfies ставятся в ABox вручную — AccessExplainer
по определению работает поверх результата reasoning, его задача —
собрать SLD-trace тела правила, а не выводить отношения заново.
AccessExplainer — приватный модуль AccessService; прежнее имя ExplanationService
не используется (код адаптирован под workspace.dsl).
"""
from __future__ import annotations

import datetime
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import AllDifferent, World  # noqa: E402

from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from services.access._explanations import AccessExplainer  # noqa: E402


class AccessExplainerTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self.core = SimpleNamespace(onto=self.onto)
        self.exp = AccessExplainer(self.core)

        with self.onto:
            self.methodist = self.onto.Methodologist("meth_exp")
            self.student = self.onto.Student("stu_exp")
            self.course = self.onto.Course("course_exp")
            self.module = self.onto.Module("mod_exp")
            self.course.has_module = [self.module]

    def tearDown(self):
        self.world.close()

    def _mark_satisfies(self, policy, student=None) -> None:
        stu = student or self.student
        existing = list(getattr(stu, "satisfies", []) or [])
        existing.append(policy)
        stu.satisfies = existing

    def _mark_available(self, element, student=None) -> None:
        stu = student or self.student
        existing = list(getattr(element, "is_available_for", []) or [])
        existing.append(stu)
        element.is_available_for = existing

    def test_completion_satisfied_has_binding(self):
        with self.onto:
            target = self.onto.Lecture("lec_comp_target")
            self.module.contains_activity = [target]
            policy = self.onto.AccessPolicy("p_comp_sat")
            policy.rule_type = "completion_required"
            policy.is_active = True
            policy.targets_element = target
            pr = self.onto.ProgressRecord("pr_comp")
            pr.refers_to_element = target
            pr.has_status = self.onto.status_completed
            self.student.has_progress_record = [pr]
        self._mark_satisfies(policy)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "satisfied")
        self.assertEqual(just.rule_template, "completion_required")
        self.assertEqual(just.variable_bindings["progress_record"], "pr_comp")
        self.assertTrue(any(f["predicate"] == "has_status" for f in just.body_facts))

    def test_grade_unsatisfied_reports_delta(self):
        with self.onto:
            target = self.onto.Test("t_grade_under")
            self.module.contains_activity = [target]
            policy = self.onto.AccessPolicy("p_grade_under")
            policy.rule_type = "grade_required"
            policy.is_active = True
            policy.targets_element = target
            policy.passing_threshold = 80.0
            pr = self.onto.ProgressRecord("pr_grade_under")
            pr.refers_to_element = target
            pr.has_grade = 60.0
            self.student.has_progress_record = [pr]

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "unsatisfied")
        self.assertEqual(just.variable_bindings["grade"], 60.0)
        self.assertEqual(just.variable_bindings["threshold"], 80.0)
        self.assertIn("60.0", just.note or "")

    def test_viewed_satisfied_binds_status(self):
        with self.onto:
            target = self.onto.Lecture("lec_view_target")
            self.module.contains_activity = [target]
            policy = self.onto.AccessPolicy("p_viewed_sat")
            policy.rule_type = "viewed_required"
            policy.is_active = True
            policy.targets_element = target
            pr = self.onto.ProgressRecord("pr_viewed")
            pr.refers_to_element = target
            pr.has_status = self.onto.status_viewed
            self.student.has_progress_record = [pr]
        self._mark_satisfies(policy)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "satisfied")
        self.assertEqual(just.variable_bindings["status"], "status_viewed")

    def test_competency_satisfied_via_inheritance_chain(self):
        with self.onto:
            parent = self.onto.Competency("comp_parent")
            child = self.onto.Competency("comp_child")
            child.is_subcompetency_of = [parent]
            policy = self.onto.AccessPolicy("p_comp_parent")
            policy.rule_type = "competency_required"
            policy.is_active = True
            policy.targets_competency = [parent]
            self.student.has_competency = [child]
        self._mark_satisfies(policy)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "satisfied")
        self.assertIn("comp_parent", just.note)
        self.assertTrue(any(
            f["predicate"] == "is_subcompetency_of" for f in just.body_facts
        ))

    def test_date_unsatisfied_reports_window_and_now(self):
        with self.onto:
            policy = self.onto.AccessPolicy("p_date_out")
            policy.rule_type = "date_restricted"
            policy.is_active = True
            policy.valid_from = datetime.datetime(2020, 1, 1)
            policy.valid_until = datetime.datetime(2020, 12, 31)
            now_ind = self.onto.CurrentTime("current_time_ind")
            now_ind.has_value = datetime.datetime(2026, 4, 22)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "unsatisfied")
        self.assertIn("вне окна", just.note)

    def test_group_unsatisfied_reports_student_groups(self):
        with self.onto:
            required = self.onto.Group("grp_advanced")
            other = self.onto.Group("grp_basic")
            policy = self.onto.AccessPolicy("p_grp_adv")
            policy.rule_type = "group_restricted"
            policy.is_active = True
            policy.restricted_to_group = required
            self.student.belongs_to_group = [other]

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "unsatisfied")
        self.assertEqual(just.variable_bindings["required_group"], "grp_advanced")
        self.assertIn("grp_basic", just.variable_bindings["student_groups"])

    def test_aggregate_satisfied_binds_contributing_grades(self):
        with self.onto:
            q1 = self.onto.Test("t_agg_1"); q2 = self.onto.Test("t_agg_2")
            self.module.contains_activity = [q1, q2]
            policy = self.onto.AccessPolicy("p_agg")
            policy.rule_type = "aggregate_required"
            policy.is_active = True
            policy.aggregate_function = "AVG"
            policy.aggregate_elements = [q1, q2]
            policy.passing_threshold = 70.0

            pr1 = self.onto.ProgressRecord("pr_agg_1"); pr1.refers_to_element = q1; pr1.has_grade = 80.0
            pr2 = self.onto.ProgressRecord("pr_agg_2"); pr2.refers_to_element = q2; pr2.has_grade = 70.0
            self.student.has_progress_record = [pr1, pr2]

            fact = self.onto.AggregateFact("agg_stu_p")
            fact.for_student = self.student
            fact.for_policy = policy
            fact.computed_value = 75.0
        self._mark_satisfies(policy)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "satisfied")
        self.assertEqual(just.variable_bindings["computed_value"], 75.0)
        self.assertEqual(len(just.variable_bindings["contributing_grades"]), 2)

    def test_and_requires_all_children(self):
        with self.onto:
            target = self.onto.Lecture("t_and")
            self.module.contains_activity = [target]
            sub_a = self.onto.AccessPolicy("p_and_a"); sub_a.rule_type = "completion_required"
            sub_a.is_active = True; sub_a.targets_element = target
            sub_b = self.onto.AccessPolicy("p_and_b"); sub_b.rule_type = "grade_required"
            sub_b.is_active = True; sub_b.targets_element = target; sub_b.passing_threshold = 90.0
            policy = self.onto.AccessPolicy("p_and")
            policy.rule_type = "and_combination"; policy.is_active = True
            policy.has_subpolicy = [sub_a, sub_b]
            AllDifferent([sub_a, sub_b])

            pr = self.onto.ProgressRecord("pr_and")
            pr.refers_to_element = target
            pr.has_status = self.onto.status_completed
            pr.has_grade = 70.0
            self.student.has_progress_record = [pr]
        # only sub_a удовлетворён, поэтому AND — unsatisfied
        self._mark_satisfies(sub_a)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "unsatisfied")
        self.assertEqual(len(just.children), 2)
        statuses = {c.policy_id: c.status for c in just.children}
        self.assertEqual(statuses["p_and_a"], "satisfied")
        self.assertEqual(statuses["p_and_b"], "unsatisfied")

    def test_or_satisfied_when_any_child_passes(self):
        with self.onto:
            comp = self.onto.Competency("c_or")
            sub_a = self.onto.AccessPolicy("p_or_a"); sub_a.rule_type = "competency_required"
            sub_a.is_active = True; sub_a.targets_competency = [comp]
            sub_b = self.onto.AccessPolicy("p_or_b"); sub_b.rule_type = "group_restricted"
            sub_b.is_active = True
            sub_b.restricted_to_group = self.onto.Group("grp_or")
            policy = self.onto.AccessPolicy("p_or")
            policy.rule_type = "or_combination"; policy.is_active = True
            policy.has_subpolicy = [sub_a, sub_b]
            self.student.has_competency = [comp]
        self._mark_satisfies(sub_a)
        self._mark_satisfies(policy)

        just = self.exp.explain_satisfies(self.student, policy)

        self.assertEqual(just.status, "satisfied")
        self.assertIn("p_or_a", just.variable_bindings["satisfied_by"])

    def test_meta_rule_collects_witnesses_per_active_policy(self):
        with self.onto:
            target = self.onto.Lecture("t_meta")
            self.module.contains_activity = [target]
            p1 = self.onto.AccessPolicy("p_meta_1"); p1.rule_type = "completion_required"
            p1.is_active = True; p1.targets_element = target
            p2 = self.onto.AccessPolicy("p_meta_2"); p2.rule_type = "grade_required"
            p2.is_active = True; p2.targets_element = target; p2.passing_threshold = 50.0
            target.has_access_policy = [p1, p2]
            pr = self.onto.ProgressRecord("pr_meta")
            pr.refers_to_element = target
            pr.has_status = self.onto.status_completed
            pr.has_grade = 70.0
            self.student.has_progress_record = [pr]
        self._mark_satisfies(p1)
        self._mark_satisfies(p2)
        self._mark_available(target)

        just = self.exp.explain_is_available(self.student, target)

        self.assertEqual(just.status, "available")
        self.assertEqual(len(just.children), 2)
        self.assertEqual({c.status for c in just.children}, {"satisfied"})

    def test_meta_rule_unavailable_when_no_policy_satisfied(self):
        with self.onto:
            target = self.onto.Lecture("t_meta_off")
            self.module.contains_activity = [target]
            p = self.onto.AccessPolicy("p_meta_off"); p.rule_type = "grade_required"
            p.is_active = True; p.targets_element = target; p.passing_threshold = 90.0
            target.has_access_policy = [p]

        just = self.exp.explain_is_available(self.student, target)

        self.assertEqual(just.status, "unavailable")
        self.assertEqual(len(just.children), 1)
        self.assertEqual(just.children[0].status, "unsatisfied")


if __name__ == "__main__":
    unittest.main()
