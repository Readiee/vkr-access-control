"""Unit-тесты VerificationService: проверка атомарной выполнимости без Pellet"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  

from core.config import DEFAULT_ONTOLOGY_PATH  
from core.cache_manager import CacheManager  
from services.verification import VerificationService  


class _StubReasoner:
    """Заглушка ReasoningOrchestrator: возвращает ok, чтобы verify прошёл СВ-1"""

    def reason(self):
        class R:
            status = "ok"
            error = None
        return R()


class AtomicUnsatisfiabilityTests(unittest.TestCase):
    """Проверки атомарной невыполнимости без запуска Pellet — по синтаксису политики"""

    def setUp(self):
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self._created: list[str] = []

        class _CoreStub:
            onto = self.onto

            class courses:
                onto_ref = self.onto

                @classmethod
                def find_by_id(cls, eid):
                    return cls.onto_ref.search_one(iri=f"*{eid}")

                @classmethod
                def get_all_elements(cls):
                    return cls.onto_ref.CourseStructure.instances()

        self.service = VerificationService(
            _CoreStub(),
            reasoner=_StubReasoner(),
            cache=CacheManager(None),
        )

    def tearDown(self):
        self.world.close()

    def _track(self, name: str) -> str:
        self._created.append(name)
        return name

    def test_grade_threshold_out_of_range(self):
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("p_atomic_grade_bad"))
            policy.rule_type = "grade_required"
            policy.is_active = True
            policy.passing_threshold = 150.0

        violations = self.service._atomic_unsatisfiable()
        found = [v for v in violations if v["policy_id"] == "p_atomic_grade_bad"]
        self.assertEqual(len(found), 1)
        self.assertIn("вне диапазона", found[0]["reason"])

    def test_date_empty_window(self):
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("p_atomic_date_bad"))
            policy.rule_type = "date_restricted"
            policy.is_active = True
            policy.valid_from = datetime(2026, 6, 1)
            policy.valid_until = datetime(2026, 5, 1)

        violations = self.service._atomic_unsatisfiable()
        found = [v for v in violations if v["policy_id"] == "p_atomic_date_bad"]
        self.assertEqual(len(found), 1)
        self.assertIn("пустое окно", found[0]["reason"])

    def test_aggregate_empty_elements(self):
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("p_atomic_agg_bad"))
            policy.rule_type = "aggregate_required"
            policy.is_active = True
            policy.aggregate_function = "AVG"
            policy.passing_threshold = 70.0
            policy.aggregate_elements = []

        violations = self.service._atomic_unsatisfiable()
        found = [v for v in violations if v["policy_id"] == "p_atomic_agg_bad"]
        self.assertEqual(len(found), 1)
        self.assertIn("aggregate_elements пуст", found[0]["reason"])

    def test_valid_policy_not_reported(self):
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("p_atomic_ok"))
            policy.rule_type = "grade_required"
            policy.is_active = True
            policy.passing_threshold = 70.0

        violations = self.service._atomic_unsatisfiable()
        self.assertFalse(any(v["policy_id"] == "p_atomic_ok" for v in violations))

    def test_inactive_policy_not_reported(self):
        """Неактивные политики не должны попадать в отчёт недостижимости."""
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("p_atomic_inactive_bad"))
            policy.rule_type = "grade_required"
            policy.is_active = False
            policy.passing_threshold = 500.0  # заведомо плохой порог

        violations = self.service._atomic_unsatisfiable()
        self.assertFalse(any(v["policy_id"] == "p_atomic_inactive_bad" for v in violations))

    def test_competency_required_without_assessor_reported(self):
        with self.onto:
            comp = self.onto.Competency(self._track("comp_atomic_unreach"))
            policy = self.onto.AccessPolicy(self._track("p_atomic_comp_unreach"))
            policy.rule_type = "competency_required"
            policy.is_active = True
            policy.targets_competency = [comp]

        violations = self.service._atomic_unsatisfiable()
        found = [v for v in violations if v["policy_id"] == "p_atomic_comp_unreach"]
        self.assertEqual(len(found), 1)
        self.assertIn("не оценивается", found[0]["reason"])


class StructuralReachabilityTests(unittest.TestCase):
    """Структурная достижимость через can_grant_element"""

    def setUp(self):
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self._created: list[str] = []

        from types import SimpleNamespace

        from services.verification import VerificationService  # local import

        core = SimpleNamespace(
            onto=self.onto,
            courses=SimpleNamespace(
                find_by_id=lambda eid: self.onto.search_one(iri=f"*{eid}"),
                get_all_elements=lambda: list(self.onto.CourseStructure.instances()),
            ),
        )
        self.service = VerificationService(
            core,
            reasoner=_StubReasoner(),
            cache=CacheManager(None),
        )

    def tearDown(self):
        self.world.close()

    def _track(self, name: str) -> str:
        self._created.append(name)
        return name

    def test_free_element_is_reachable(self):
        with self.onto:
            course = self.onto.Course(self._track("course_reach_free"))
            lec = self.onto.Lecture(self._track("lec_reach_free"))
            course.has_module = []
            course.contains_activity = [lec]

        cache = {}
        self.assertTrue(
            self.service._can_grant_element(lec, visited=set(), cache=cache, unsat_policies=set())
        )

    def test_chain_unreachable_via_dead_policy(self):
        """Цепочка A → B, где A защищён неудовлетворимой политикой → оба недостижимы."""
        with self.onto:
            course = self.onto.Course(self._track("course_reach_chain"))
            a = self.onto.Lecture(self._track("lec_reach_a"))
            b = self.onto.Lecture(self._track("lec_reach_b"))
            course.contains_activity = [a, b]

            bad_policy = self.onto.AccessPolicy(self._track("p_reach_bad"))
            bad_policy.rule_type = "grade_required"
            bad_policy.is_active = True
            bad_policy.passing_threshold = 500.0  # out of range
            bad_policy.targets_element = a
            a.has_access_policy = [bad_policy]

            b_policy = self.onto.AccessPolicy(self._track("p_reach_b_depends"))
            b_policy.rule_type = "completion_required"
            b_policy.is_active = True
            b_policy.targets_element = a
            b.has_access_policy = [b_policy]

        reports = self.service._find_unreachable(course)
        unreachable_ids = {r.get("element_id") for r in reports if r.get("code") == "SV3_UNREACHABLE"}
        atomic_ids = {r.get("policy_id") for r in reports if r.get("code") == "SV3_ATOMIC_UNSAT"}
        self.assertIn("p_reach_bad", atomic_ids)
        self.assertIn("lec_reach_a", unreachable_ids)
        self.assertIn("lec_reach_b", unreachable_ids)

    def test_self_cycle_unreachable(self):
        """Элемент ссылается сам на себя через completion_required → недостижим."""
        with self.onto:
            course = self.onto.Course(self._track("course_reach_self"))
            x = self.onto.Lecture(self._track("lec_reach_self"))
            course.contains_activity = [x]

            self_policy = self.onto.AccessPolicy(self._track("p_reach_self"))
            self_policy.rule_type = "completion_required"
            self_policy.is_active = True
            self_policy.targets_element = x
            x.has_access_policy = [self_policy]

        cache = {}
        self.assertFalse(
            self.service._can_grant_element(x, visited=set(), cache=cache, unsat_policies=set())
        )

    def test_or_combination_reaches_via_one_branch(self):
        """OR-композит проходит, если достижима хотя бы одна подполитика."""
        with self.onto:
            course = self.onto.Course(self._track("course_reach_or"))
            ok = self.onto.Lecture(self._track("lec_reach_or_ok"))
            target = self.onto.Lecture(self._track("lec_reach_or_target"))
            course.contains_activity = [ok, target]

            sub_ok = self.onto.AccessPolicy(self._track("p_reach_or_sub_ok"))
            sub_ok.rule_type = "completion_required"
            sub_ok.is_active = True
            sub_ok.targets_element = ok

            sub_bad = self.onto.AccessPolicy(self._track("p_reach_or_sub_bad"))
            sub_bad.rule_type = "grade_required"
            sub_bad.is_active = True
            sub_bad.passing_threshold = 500.0

            composite = self.onto.AccessPolicy(self._track("p_reach_or"))
            composite.rule_type = "or_combination"
            composite.is_active = True
            composite.has_subpolicy = [sub_ok, sub_bad]
            target.has_access_policy = [composite]

        reports = self.service._find_unreachable(course)
        unreachable_ids = {r.get("element_id") for r in reports if r.get("code") == "SV3_UNREACHABLE"}
        self.assertNotIn("lec_reach_or_target", unreachable_ids)

    def test_and_combination_fails_if_one_sub_unsatisfiable(self):
        """AND недостижим, даже если один из подполиси невозможен."""
        with self.onto:
            course = self.onto.Course(self._track("course_reach_and"))
            ok = self.onto.Lecture(self._track("lec_reach_and_ok"))
            target = self.onto.Lecture(self._track("lec_reach_and_target"))
            course.contains_activity = [ok, target]

            sub_ok = self.onto.AccessPolicy(self._track("p_reach_and_sub_ok"))
            sub_ok.rule_type = "completion_required"
            sub_ok.is_active = True
            sub_ok.targets_element = ok

            sub_bad = self.onto.AccessPolicy(self._track("p_reach_and_sub_bad"))
            sub_bad.rule_type = "date_restricted"
            sub_bad.is_active = True
            # пустое окно — атомарно невыполнима
            from datetime import datetime as _dt
            sub_bad.valid_from = _dt(2026, 12, 31)
            sub_bad.valid_until = _dt(2026, 1, 1)

            composite = self.onto.AccessPolicy(self._track("p_reach_and"))
            composite.rule_type = "and_combination"
            composite.is_active = True
            composite.has_subpolicy = [sub_ok, sub_bad]
            target.has_access_policy = [composite]

        reports = self.service._find_unreachable(course)
        unreachable_ids = {r.get("element_id") for r in reports if r.get("code") == "SV3_UNREACHABLE"}
        self.assertIn("lec_reach_and_target", unreachable_ids)


if __name__ == "__main__":
    unittest.main()
