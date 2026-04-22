"""Integration: date_restricted и group_restricted через SWRL + Pellet.

FIX11 e2e: после сноса DateAccessFilter проверяем, что элемент за пределами
окна не получает is_available_for. FIX8 e2e: group_restricted пропускает только
членов нужной группы.
"""
from __future__ import annotations

import os
import shutil
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from core.enums import ElementType  # noqa: E402
from schemas.schemas import CourseElement, CourseSyncPayload  # noqa: E402
from services.access_service import AccessService  # noqa: E402
from services.course_service import CourseService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402


class DateAndGroupReasoningTests(unittest.TestCase):
    def setUp(self):
        self.test_owl = "test_date_group.owl"
        shutil.copy(DEFAULT_ONTOLOGY_PATH, self.test_owl)
        self.core = OntologyCore(self.test_owl)
        self.course_service = CourseService(self.core)
        self.access_service = AccessService(self.core)

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
        self.course_service.sync_course_structure(
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
            self.p_date_future.rule_type = ["date_restricted"]
            self.p_date_future.is_active = [True]
            self.p_date_future.valid_from = [datetime(2099, 1, 1)]
            self.p_date_future.valid_until = [datetime(2099, 12, 31)]
            self.lec_date.has_access_policy = [self.p_date_future]

            # group-policy: только grp_dg_in
            self.p_group = self.core.onto.AccessPolicy("policy_dg_group_only")
            self.p_group.rule_type = ["group_restricted"]
            self.p_group.is_active = [True]
            self.p_group.restricted_to_group = [self.grp_in]
            self.lec_group.has_access_policy = [self.p_group]

        self.core.save()

    def tearDown(self):
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    def test_date_outside_window_closes_element_through_swrl(self):
        """FIX11: окно в будущем → SWRL не выводит satisfies → элемент закрыт."""
        result = self.core.run_reasoner()
        self.assertEqual(result.status, "ok")

        available_member = self.access_service.rebuild_student_access("dg_member")[
            "inferred_available_elements"
        ]
        self.assertNotIn("lec_dg_date", available_member,
                         "date-restricted элемент вне окна не должен быть доступен")

    def test_date_inside_window_opens_element(self):
        """Когда окно включает «сейчас» — элемент открыт через SWRL-шаблон 5."""
        with self.core.onto:
            self.p_date_future.valid_from = [datetime(2020, 1, 1)]
            self.p_date_future.valid_until = [datetime(2099, 12, 31)]
        self.core.save()
        result = self.core.run_reasoner()
        self.assertEqual(result.status, "ok")

        available = self.access_service.rebuild_student_access("dg_member")[
            "inferred_available_elements"
        ]
        self.assertIn("lec_dg_date", available)

    def test_group_restricted_opens_for_member_only(self):
        """group_restricted: член группы видит, чужой — нет."""
        result = self.core.run_reasoner()
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
