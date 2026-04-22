"""Unit-тесты AccessService: CWA-enforcement + каскадная блокировка + UC-9 explain

is_available_for ставится в ABox вручную (имитация результата reasoning) —
Pellet не запускается, это чисто логика слоя доступа
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  # noqa: E402

from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from services.access_service import AccessService  # noqa: E402


class _InMemoryCache:
    def __init__(self):
        self.storage: dict = {}

    def get_student_access(self, student_id: str):
        return self.storage.get(student_id)

    def set_student_access(self, student_id: str, data):
        self.storage[student_id] = data


class AccessServiceTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self._created: list[str] = []

        with self.onto:
            self.student = self.onto.Student(self._track("student_acc_ivan"))
            self.course = self.onto.Course(self._track("course_acc"))
            self.module = self.onto.Module(self._track("mod_acc"))
            self.lec_free = self.onto.Lecture(self._track("lec_acc_free"))
            self.lec_guarded = self.onto.Lecture(self._track("lec_acc_guarded"))
            self.course.has_module = [self.module]
            self.module.contains_element = [self.lec_free, self.lec_guarded]

            self.policy = self.onto.AccessPolicy(self._track("p_acc_guard"))
            self.policy.rule_type = ["completion_required"]
            self.policy.is_active = [True]
            self.policy.targets_element = [self.lec_free]
            self.lec_guarded.has_access_policy = [self.policy]

        # Стаб OntologyCore: только то, что реально зовёт AccessService.
        self.cache = _InMemoryCache()
        self.core = SimpleNamespace(
            onto=self.onto,
            cache=self.cache,
            courses=SimpleNamespace(
                find_by_id=lambda eid: self.onto.search_one(iri=f"*{eid}"),
                get_all_elements=lambda: list(self.onto.CourseStructure.instances()),
            ),
            students=SimpleNamespace(get_or_create=lambda sid: self.student),
        )
        self.service = AccessService(self.core)

    def tearDown(self):
        self.world.close()

    def _track(self, name: str) -> str:
        self._created.append(name)
        return name

    def test_default_allow_for_elements_without_policy(self):
        """Элементы без has_access_policy доступны по default-allow."""
        result = self.service.rebuild_student_access("acc_ivan")
        self.assertIn("course_acc", result["inferred_available_elements"])
        self.assertIn("mod_acc", result["inferred_available_elements"])
        self.assertIn("lec_acc_free", result["inferred_available_elements"])

    def test_cwa_deny_when_satisfies_absent(self):
        """Элемент с активной политикой и без is_available_for — закрыт (default-deny)."""
        result = self.service.rebuild_student_access("acc_ivan")
        self.assertNotIn("lec_acc_guarded", result["inferred_available_elements"])

    def test_cwa_open_when_is_available_for_set(self):
        """Как только Pellet (или мы вручную) ставит is_available_for — элемент открыт."""
        self.lec_guarded.is_available_for = [self.student]
        result = self.service.rebuild_student_access("acc_ivan")
        self.assertIn("lec_acc_guarded", result["inferred_available_elements"])

    def test_cascade_block_through_parent(self):
        """Ребёнок без своих политик скрыт, если родитель закрыт активной политикой."""
        # Вешаем на module_acc активную политику, которую студент не удовлетворяет
        with self.onto:
            parent_policy = self.onto.AccessPolicy(self._track("p_acc_parent"))
            parent_policy.rule_type = ["completion_required"]
            parent_policy.is_active = [True]
            parent_policy.targets_element = [self.lec_guarded]
            self.module.has_access_policy = [parent_policy]

        result = self.service.rebuild_student_access("acc_ivan")
        # lec_acc_free висит под закрытым mod_acc → скрыт каскадом
        self.assertNotIn("lec_acc_free", result["inferred_available_elements"])
        self.assertNotIn("mod_acc", result["inferred_available_elements"])

    def test_get_course_access_filters_by_course_scope(self):
        """В ответе только элементы запрошенного курса + каскадная фильтрация."""
        # Положить в cache что-то из чужого курса тоже
        self.cache.storage["acc_ivan"] = {
            "course_acc": {},
            "mod_acc": {},
            "lec_acc_free": {},
            "foreign_course_element": {},
        }
        result = self.service.get_course_access("acc_ivan", "course_acc")
        self.assertIn("course_acc", result["available_elements"])
        self.assertIn("lec_acc_free", result["available_elements"])
        self.assertNotIn("foreign_course_element", result["available_elements"])

    def test_explain_blocking_reports_unsatisfied_policy(self):
        """explain_blocking возвращает failure_reason + is_available=False."""
        report = self.service.explain_blocking("acc_ivan", "lec_acc_guarded")
        self.assertFalse(report["is_available"])
        self.assertIsNone(report["cascade_blocker"])
        self.assertEqual(len(report["applicable_policies"]), 1)
        policy_entry = report["applicable_policies"][0]
        self.assertFalse(policy_entry["satisfied"])
        self.assertIsNotNone(policy_entry["failure_reason"])
        self.assertEqual(policy_entry["rule_type"], "completion_required")

    def test_explain_blocking_reports_cascade(self):
        """Когда родитель закрыт — в отчёте указан cascade_blocker."""
        with self.onto:
            parent_policy = self.onto.AccessPolicy(self._track("p_acc_cascade"))
            parent_policy.rule_type = ["completion_required"]
            parent_policy.is_active = [True]
            parent_policy.targets_element = [self.lec_guarded]
            self.module.has_access_policy = [parent_policy]

        report = self.service.explain_blocking("acc_ivan", "lec_acc_free")
        self.assertEqual(report["cascade_blocker"], "mod_acc")
        self.assertFalse(report["is_available"])

    def test_explain_blocking_positive_justification_tree(self):
        """Когда элемент доступен — trace раскрывает meta:is_available_for + тело шаблона."""
        self.lec_guarded.is_available_for = [self.student]
        self.student.satisfies = [self.policy]

        report = self.service.explain_blocking("acc_ivan", "lec_acc_guarded")

        self.assertTrue(report["is_available"])
        just = report["justification"]
        self.assertEqual(just["status"], "available")
        self.assertEqual(just["rule_template"], "meta:is_available_for")
        self.assertEqual(len(just["children"]), 1)
        child = just["children"][0]
        self.assertEqual(child["status"], "satisfied")
        self.assertEqual(child["rule_template"], "completion_required")

    def test_explain_blocking_default_allow_justification(self):
        """Элемент без активных политик — justification фиксирует default_allow."""
        report = self.service.explain_blocking("acc_ivan", "lec_acc_free")

        just = report["justification"]
        self.assertEqual(just["rule_template"], "default_allow")
        self.assertEqual(just["status"], "available")


if __name__ == "__main__":
    unittest.main()
