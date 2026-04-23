"""Unit-тесты SubsumptionChecker: СВ-4 Redundancy + СВ-5 Subsumption."""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from owlready2 import AllDifferent, World, destroy_entity  # noqa: E402

from services.verification._subsumption import SubsumptionChecker  # noqa: E402


class SubsumptionCheckerTests(unittest.TestCase):
    """Изолированный World на каждый тест — иначе индивиды из других test-файлов
    накапливаются в default_world и SubsumptionChecker видит чужие политики."""

    def setUp(self):
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self._created: list[str] = []

    def tearDown(self):
        self.world.close()

    def _track(self, name: str) -> str:
        self._created.append(name)
        return name

    def test_redundant_grade_policies_detected(self):
        with self.onto:
            quiz = self.onto.Test(self._track("quiz_sub1"))
            module = self.onto.Module(self._track("mod_sub_target"))
            target = self.onto.Test(self._track("test_sub_target"))

            p_strong = self.onto.AccessPolicy(self._track("p_sub_strong"))
            p_strong.rule_type = "grade_required"
            p_strong.is_active = True
            p_strong.passing_threshold = 80.0
            p_strong.targets_element = target

            p_weak = self.onto.AccessPolicy(self._track("p_sub_weak"))
            p_weak.rule_type = "grade_required"
            p_weak.is_active = True
            p_weak.passing_threshold = 60.0
            p_weak.targets_element = target

            module.has_access_policy = [p_strong, p_weak]

        reports = SubsumptionChecker(self.onto).find_all()
        kinds = {r.kind for r in reports}
        self.assertIn("redundancy", kinds)
        pair = next(r for r in reports if r.kind == "redundancy")
        self.assertEqual(pair.dominant, "p_sub_weak")   # более слабое поглощает более сильное
        self.assertEqual(pair.dominated, "p_sub_strong")

    def test_subject_subsumption_group(self):
        with self.onto:
            g_wide = self.onto.Group(self._track("grp_sub_wide"))
            g_narrow = self.onto.Group(self._track("grp_sub_narrow"))
            st1 = self.onto.Student(self._track("student_sub1"))
            st2 = self.onto.Student(self._track("student_sub2"))
            st1.belongs_to_group = [g_wide, g_narrow]
            st2.belongs_to_group = [g_wide]

            element = self.onto.Lecture(self._track("lec_sub_elem"))
            p_wide = self.onto.AccessPolicy(self._track("p_sub_wide"))
            p_wide.rule_type = "group_restricted"
            p_wide.is_active = True
            p_wide.restricted_to_group = g_wide

            p_narrow = self.onto.AccessPolicy(self._track("p_sub_narrow"))
            p_narrow.rule_type = "group_restricted"
            p_narrow.is_active = True
            p_narrow.restricted_to_group = g_narrow

            element.has_access_policy = [p_wide, p_narrow]

        reports = SubsumptionChecker(self.onto).find_all()
        subject = [r for r in reports if r.kind == "subject_subsumption"]
        self.assertEqual(len(subject), 1)
        self.assertEqual(subject[0].dominant, "p_sub_wide")
        self.assertEqual(subject[0].dominated, "p_sub_narrow")

    def test_date_window_subsumption(self):
        with self.onto:
            element = self.onto.Lecture(self._track("lec_sub_date"))
            p_wide = self.onto.AccessPolicy(self._track("p_sub_date_wide"))
            p_wide.rule_type = "date_restricted"
            p_wide.is_active = True
            p_wide.valid_from = datetime(2026, 1, 1)
            p_wide.valid_until = datetime(2026, 12, 31)

            p_narrow = self.onto.AccessPolicy(self._track("p_sub_date_narrow"))
            p_narrow.rule_type = "date_restricted"
            p_narrow.is_active = True
            p_narrow.valid_from = datetime(2026, 5, 1)
            p_narrow.valid_until = datetime(2026, 6, 30)

            element.has_access_policy = [p_wide, p_narrow]

        reports = SubsumptionChecker(self.onto).find_all()
        dates = [r for r in reports if "окно" in r.witness]
        self.assertTrue(dates)
        self.assertEqual(dates[0].dominant, "p_sub_date_wide")
        self.assertEqual(dates[0].dominated, "p_sub_date_narrow")


    def test_independent_policies_not_subsumed(self):
        """Две grade-политики с разными target не должны давать redundancy."""
        with self.onto:
            element = self.onto.Module(self._track("mod_sub_indep"))
            t1 = self.onto.Test(self._track("test_sub_indep_a"))
            t2 = self.onto.Test(self._track("test_sub_indep_b"))

            p1 = self.onto.AccessPolicy(self._track("p_sub_indep_a"))
            p1.rule_type = "grade_required"
            p1.is_active = True
            p1.passing_threshold = 70.0
            p1.targets_element = t1

            p2 = self.onto.AccessPolicy(self._track("p_sub_indep_b"))
            p2.rule_type = "grade_required"
            p2.is_active = True
            p2.passing_threshold = 70.0
            p2.targets_element = t2

            element.has_access_policy = [p1, p2]

        reports = SubsumptionChecker(self.onto).find_all()
        pair_names = {(r.dominant, r.dominated) for r in reports}
        self.assertNotIn(("p_sub_indep_a", "p_sub_indep_b"), pair_names)
        self.assertNotIn(("p_sub_indep_b", "p_sub_indep_a"), pair_names)

    def test_inactive_policy_ignored(self):
        """Неактивная политика не должна участвовать в subsumption."""
        with self.onto:
            element = self.onto.Module(self._track("mod_sub_inact"))
            target = self.onto.Test(self._track("test_sub_inact"))

            p_inactive = self.onto.AccessPolicy(self._track("p_sub_inactive"))
            p_inactive.rule_type = "grade_required"
            p_inactive.is_active = False
            p_inactive.passing_threshold = 60.0
            p_inactive.targets_element = target

            p_active = self.onto.AccessPolicy(self._track("p_sub_active"))
            p_active.rule_type = "grade_required"
            p_active.is_active = True
            p_active.passing_threshold = 80.0
            p_active.targets_element = target

            element.has_access_policy = [p_inactive, p_active]

        reports = SubsumptionChecker(self.onto).find_all()
        self.assertFalse(
            any(r.dominant == "p_sub_inactive" or r.dominated == "p_sub_inactive" for r in reports),
            "неактивная политика не должна попадать в отчёт",
        )

    def test_equal_thresholds_not_reported(self):
        """Два правила с одинаковым порогом — это параллельные, не subsumption."""
        with self.onto:
            element = self.onto.Module(self._track("mod_sub_eq"))
            target = self.onto.Test(self._track("test_sub_eq"))

            p1 = self.onto.AccessPolicy(self._track("p_sub_eq_1"))
            p1.rule_type = "grade_required"
            p1.is_active = True
            p1.passing_threshold = 70.0
            p1.targets_element = target

            p2 = self.onto.AccessPolicy(self._track("p_sub_eq_2"))
            p2.rule_type = "grade_required"
            p2.is_active = True
            p2.passing_threshold = 70.0
            p2.targets_element = target

            element.has_access_policy = [p1, p2]

        reports = SubsumptionChecker(self.onto).find_all()
        grade_reports = [r for r in reports if "grade" in r.witness]
        self.assertEqual(grade_reports, [], "равные пороги → параллельные, не subsumption")

    def test_and_composite_subsumed_by_atomic_equivalent_subpolicy(self):
        """p_all (grade≥70) поглощает p_and = AND(grade≥70, group_restricted)."""
        with self.onto:
            element = self.onto.Lecture(self._track("elem_sub_and"))
            target = self.onto.Test(self._track("quiz_sub_and"))
            group = self.onto.Group(self._track("grp_sub_and"))

            wide = self.onto.AccessPolicy(self._track("p_sub_and_wide"))
            wide.rule_type = "grade_required"
            wide.is_active = True
            wide.passing_threshold = 70.0
            wide.targets_element = target

            sub_grade = self.onto.AccessPolicy(self._track("p_sub_and_sub_grade"))
            sub_grade.rule_type = "grade_required"
            sub_grade.is_active = True
            sub_grade.passing_threshold = 70.0
            sub_grade.targets_element = target

            sub_group = self.onto.AccessPolicy(self._track("p_sub_and_sub_group"))
            sub_group.rule_type = "group_restricted"
            sub_group.is_active = True
            sub_group.restricted_to_group = group

            narrow = self.onto.AccessPolicy(self._track("p_sub_and_narrow"))
            narrow.rule_type = "and_combination"
            narrow.is_active = True
            narrow.has_subpolicy = [sub_grade, sub_group]
            AllDifferent([sub_grade, sub_group])

            element.has_access_policy = [wide, narrow]

        reports = SubsumptionChecker(self.onto).find_all()
        pairs = [(r.dominant, r.dominated, r.kind) for r in reports]
        self.assertIn(("p_sub_and_wide", "p_sub_and_narrow", "subject_subsumption"), pairs)


if __name__ == "__main__":
    unittest.main()
