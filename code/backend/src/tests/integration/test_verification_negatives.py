"""Integration: негативные сценарии СВ-1 (inconsistency) и СВ-3 (reachability failed)

Строим минимальные bad-case ABox прямо поверх онтологии
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  # noqa: E402

from core.enums import ElementType  # noqa: E402
from schemas.schemas import CourseElement, CourseSyncPayload  # noqa: E402
from services.integration_service import IntegrationService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402
from services.policy_service import PolicyService  # noqa: E402
from services.verification import VerificationService  # noqa: E402


class VerificationNegativeTests(unittest.TestCase):
    """Каждый тест — свежий owlready2 World, иначе индивиды из прошлого теста
    остаются в глобальном графе и портят Pellet."""

    def setUp(self):
        from tests._factory import make_temp_onto_copy
        self.test_owl = make_temp_onto_copy(prefix="vkr_verify_neg_")
        self.world = World()
        self.core = OntologyCore(self.test_owl, world=self.world)
        from services.cache_manager import CacheManager
        from services.reasoning import ReasoningOrchestrator
        from services.rollup_service import RollupService
        from services.access import AccessService
        from services.verification import VerificationService
        self.cache = CacheManager(None)
        self.reasoner = ReasoningOrchestrator(self.core.onto)
        self.rollup = RollupService(self.core)
        self.access = AccessService(self.core, cache=self.cache, reasoner=self.reasoner)
        self.verification = VerificationService(self.core, reasoner=self.reasoner, cache=self.cache)
        self.integration_service = IntegrationService(self.core, verification=self.verification, cache=self.cache)
        self.policy_service = PolicyService(self.core, reasoner=self.reasoner, cache=self.cache)
        self.verification = VerificationService(self.core, reasoner=self.reasoner, cache=self.cache)

    def tearDown(self):
        self.world.close()
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    # СВ-1 happy-case (onto → inconsistent → отчёт failed) покрыт настоящим Pellet в
    # tests/integration/test_verification_scenarios.py::test_bad_sv1_consistency_failed
    # на сценарии bad_sv1_disjointness. Здесь остаётся только ветка timeout/error,
    # её через реальный Pellet не воспроизвести.

    def test_sv1_timeout_returns_partial_unknown(self):
        """При reasoning timeout отчёт помечается partial=True."""
        self.integration_service.sync_course_structure(
            "course_neg_timeout",
            CourseSyncPayload(
                course_name="NT",
                elements=[
                    CourseElement(
                        element_id="mod_neg_t",
                        name="M",
                        element_type=ElementType.MODULE,
                        parent_id="course_neg_timeout",
                    )
                ],
            ),
        )

        from services.reasoning import ReasoningResult
        self.reasoner.reason = lambda: ReasoningResult(status="timeout", timed_out=True)

        report = self.verification.verify("course_neg_timeout").to_dict()
        self.assertTrue(report["partial"])
        self.assertEqual(report["properties"]["consistency"]["status"], "unknown")

    def test_sv3_reachability_failed_atomic(self):
        """bad_sv3_atomic: политика с threshold=150 → атомарно недостижима."""
        self.integration_service.sync_course_structure(
            "course_neg3a",
            CourseSyncPayload(
                course_name="Neg3a",
                elements=[
                    CourseElement(
                        element_id="mod_neg3a",
                        name="M",
                        element_type=ElementType.MODULE,
                        parent_id="course_neg3a",
                    ),
                    CourseElement(
                        element_id="lec_neg3a_a",
                        name="A",
                        element_type=ElementType.LECTURE,
                        parent_id="mod_neg3a",
                    ),
                    CourseElement(
                        element_id="lec_neg3a_b",
                        name="B",
                        element_type=ElementType.LECTURE,
                        parent_id="mod_neg3a",
                    ),
                ],
            ),
        )

        # Вручную вешаем плохой threshold (PolicyService.create_policy валидирует через Pydantic,
        # но дело не в валидации — нам нужна политика с out-of-range threshold для А4 прохода 1)
        with self.core.onto:
            target = self.core.onto.search_one(iri="*lec_neg3a_a")
            source = self.core.onto.search_one(iri="*lec_neg3a_b")
            bad = self.core.onto.AccessPolicy("p_neg3a_bad_threshold")
            bad.rule_type = "grade_required"
            bad.is_active = True
            bad.passing_threshold = 150.0
            bad.targets_element = target
            source.has_access_policy = [bad]
        self.core.save()

        report = self.verification.verify("course_neg3a").to_dict()
        self.assertEqual(report["properties"]["reachability"]["status"], "failed")
        reasons = report["properties"]["reachability"]["violations"]
        self.assertTrue(any(r.get("code") == "SV3_ATOMIC_UNSAT" for r in reasons))

    def test_sv2_cycle_reported_in_full_report(self):
        """СВ-2 должен ловить настоящий цикл после insert напрямую в ABox (обход check_for_cycles)"""
        self.integration_service.sync_course_structure(
            "course_neg2",
            CourseSyncPayload(
                course_name="Neg2",
                elements=[
                    CourseElement(
                        element_id="mod_neg2_a",
                        name="MA",
                        element_type=ElementType.MODULE,
                        parent_id="course_neg2",
                    ),
                    CourseElement(
                        element_id="mod_neg2_b",
                        name="MB",
                        element_type=ElementType.MODULE,
                        parent_id="course_neg2",
                    ),
                ],
            ),
        )
        with self.core.onto:
            a = self.core.onto.search_one(iri="*mod_neg2_a")
            b = self.core.onto.search_one(iri="*mod_neg2_b")
            p_ab = self.core.onto.AccessPolicy("p_neg2_ab")
            p_ab.rule_type = "completion_required"
            p_ab.is_active = True
            p_ab.targets_element = b
            a.has_access_policy = [p_ab]
            p_ba = self.core.onto.AccessPolicy("p_neg2_ba")
            p_ba.rule_type = "completion_required"
            p_ba.is_active = True
            p_ba.targets_element = a
            b.has_access_policy = [p_ba]
        self.core.save()

        report = self.verification.verify("course_neg2").to_dict()
        self.assertEqual(report["properties"]["acyclicity"]["status"], "failed")
        cycles = report["properties"]["acyclicity"]["violations"]
        self.assertTrue(cycles)
        nodes = {n for c in cycles for n in c.get("path", [])}
        self.assertTrue({"mod_neg2_a", "mod_neg2_b"}.issubset(nodes))


if __name__ == "__main__":
    unittest.main()
