"""Integration: date_restricted и group_restricted через SWRL + Pellet

date e2e: проверяем, что элемент за пределами окна не получает is_available_for.
group e2e: group_restricted пропускает только членов нужной группы
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.enums import ElementType  # noqa: E402
from schemas.schemas import CourseElement, CourseSyncPayload  # noqa: E402
from services.access import AccessService  # noqa: E402
from services.integration_service import IntegrationService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402


class DateAndGroupReasoningTests(unittest.TestCase):
    def setUp(self):
        from tests._factory import make_temp_onto_copy
        self.test_owl = make_temp_onto_copy(prefix="vkr_date_group_")
        self.core = OntologyCore(self.test_owl)
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
        self.access_service = AccessService(self.core, cache=self.cache, reasoner=self.reasoner)

        elements = [
            CourseElement(
                element_id="mod_dg",
                name="DG Module",
                element_type=ElementType.MODULE,
                parent_id="course_dg",
            ),
            CourseElement(
                element_id="lec_dg_date",
                name="Date-guarded lecture",
                element_type=ElementType.LECTURE,
                parent_id="mod_dg",
            ),
            CourseElement(
                element_id="lec_dg_group",
                name="Group-guarded lecture",
                element_type=ElementType.LECTURE,
                parent_id="mod_dg",
            ),
        ]
        self.integration_service.sync_course_structure(
            "course_dg", CourseSyncPayload(course_name="Date+Group course", elements=elements)
        )

        with self.core.onto:
            self.grp_in = self.core.onto.Group("grp_dg_in")
            self.grp_out = self.core.onto.Group("grp_dg_out")
            self.student_member = self.core.onto.Student("student_dg_member")
            self.student_outsider = self.core.onto.Student("student_dg_outsider")
            self.student_member.belongs_to_group = [self.grp_in]
            self.student_outsider.belongs_to_group = [self.grp_out]

            self.lec_date = self.core.onto.search_one(iri="*lec_dg_date")
            self.lec_group = self.core.onto.search_one(iri="*lec_dg_group")

            # date-policy: окно в будущем (2099), сейчас вне окна
            self.p_date_future = self.core.onto.AccessPolicy("policy_dg_date_future")
            self.p_date_future.rule_type = "date_restricted"
            self.p_date_future.is_active = True
            self.p_date_future.valid_from = datetime(2099, 1, 1)
            self.p_date_future.valid_until = datetime(2099, 12, 31)
            self.lec_date.has_access_policy = [self.p_date_future]

            # group-policy: только grp_dg_in
            self.p_group = self.core.onto.AccessPolicy("policy_dg_group_only")
            self.p_group.rule_type = "group_restricted"
            self.p_group.is_active = True
            self.p_group.restricted_to_group = self.grp_in
            self.lec_group.has_access_policy = [self.p_group]

        self.core.save()

    def tearDown(self):
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    def test_date_outside_window_closes_element_through_swrl(self):
        """Окно в будущем → SWRL не выводит satisfies → элемент закрыт"""
        result = self.reasoner.reason()
        self.assertEqual(result.status, "ok")

        available_member = self.access_service.rebuild_student_access("dg_member")[
            "inferred_available_elements"
        ]
        self.assertNotIn("lec_dg_date", available_member,
                         "date-restricted элемент вне окна не должен быть доступен")

    def test_date_inside_window_opens_element(self):
        """Когда окно включает «сейчас» — элемент открыт через SWRL-шаблон 5."""
        with self.core.onto:
            self.p_date_future.valid_from = datetime(2020, 1, 1)
            self.p_date_future.valid_until = datetime(2099, 12, 31)
        self.core.save()
        result = self.reasoner.reason()
        self.assertEqual(result.status, "ok")

        available = self.access_service.rebuild_student_access("dg_member")[
            "inferred_available_elements"
        ]
        self.assertIn("lec_dg_date", available)

    def test_group_restricted_opens_for_member_only(self):
        """group_restricted: член группы видит, чужой — нет."""
        result = self.reasoner.reason()
        self.assertEqual(result.status, "ok")

        avail_member = self.access_service.rebuild_student_access("dg_member")[
            "inferred_available_elements"
        ]
        avail_outsider = self.access_service.rebuild_student_access("dg_outsider")[
            "inferred_available_elements"
        ]
        self.assertIn("lec_dg_group", avail_member)
        self.assertNotIn("lec_dg_group", avail_outsider)


if __name__ == "__main__":
    unittest.main()
