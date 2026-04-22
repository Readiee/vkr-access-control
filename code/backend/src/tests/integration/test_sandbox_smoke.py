"""FIX15 smoke-тест симулятора (UC-7a/b/c) после переделки SWRL на двухуровневую
семантику, сноса DateAccessFilter и выноса чтения доступа в AccessService.

Проверяет, что симулятор работает end-to-end на реальном Pellet:
- UC-7a: сброс песочницы
- UC-7b: симуляция прогресса и компетенций
- UC-7c: состояние песочницы (доступы + прогресс)
"""
from __future__ import annotations

import os
import shutil
import sys
import unittest
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  # noqa: E402

from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from core.enums import ElementType, RuleType, ProgressStatus  # noqa: E402
from schemas.schemas import CourseElement, CourseSyncPayload, PolicyCreate  # noqa: E402
from services.course_service import CourseService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402
from services.policy_service import PolicyService  # noqa: E402
from services.progress_service import ProgressService  # noqa: E402
from services.sandbox_service import SandboxService  # noqa: E402


class SandboxSmokeTests(unittest.TestCase):
    def setUp(self):
        self.test_owl = f"test_sandbox_smoke_{id(self)}.owl"
        shutil.copy(DEFAULT_ONTOLOGY_PATH, self.test_owl)
        self.world = World()
        self.core = OntologyCore(self.test_owl, world=self.world)
        self.course_service = CourseService(self.core)
        self.policy_service = PolicyService(self.core)
        self.progress_service = ProgressService(self.core)
        self.sandbox = SandboxService(self.core, self.progress_service)

        elements = [
            CourseElement(
                element_id="mod_sb",
                name="Sandbox module",
                element_type=ElementType.MODULE,
                parent_id="course_sb",
            ),
            CourseElement(
                element_id="test_sb",
                name="Sandbox test",
                element_type=ElementType.TEST,
                parent_id="mod_sb",
            ),
            CourseElement(
                element_id="final_sb",
                name="Sandbox final",
                element_type=ElementType.TEST,
                parent_id="mod_sb",
            ),
        ]
        self.course_service.sync_course_structure(
            "course_sb", CourseSyncPayload(course_name="Sandbox smoke", elements=elements)
        )

        self.policy_service.create_policy(PolicyCreate(
            source_element_id="final_sb",
            rule_type=RuleType.GRADE,
            target_element_id="test_sb",
            passing_threshold=70.0,
            author_id="methodologist_smirnov",
        ))

    def tearDown(self):
        self.world.close()
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    def test_uc7c_initial_state_blocks_guarded_element(self):
        """UC-7c: тестовый студент без прогресса → final_sb закрыт."""
        state = self.sandbox.get_sandbox_state("course_sb")
        avail = state.get("available_elements", [])
        self.assertIn("mod_sb", avail)
        self.assertIn("test_sb", avail)
        self.assertNotIn("final_sb", avail)

    def test_uc7b_simulate_progress_opens_element(self):
        """UC-7b: симуляция прогресса с оценкой → SWRL выводит satisfies → final открывается."""
        self.sandbox.simulate_progress(SimpleNamespace(
            element_id="test_sb",
            status=ProgressStatus.COMPLETED.value,
            grade=85.0,
        ))
        state = self.sandbox.get_sandbox_state("course_sb")
        self.assertIn("final_sb", state.get("available_elements", []))

    def test_uc7a_reset_clears_progress(self):
        """UC-7a: reset удаляет прогресс — final_sb снова закрыт."""
        self.sandbox.simulate_progress(SimpleNamespace(
            element_id="test_sb",
            status=ProgressStatus.COMPLETED.value,
            grade=85.0,
        ))
        self.sandbox.reset_all()
        state = self.sandbox.get_sandbox_state("course_sb")
        self.assertNotIn("final_sb", state.get("available_elements", []))
        self.assertEqual(state.get("progress"), {})

    def test_rollback_single_element_restores_blocking(self):
        """rollback_progress на конкретный элемент отрезает доступ через его политику."""
        self.sandbox.simulate_progress(SimpleNamespace(
            element_id="test_sb",
            status=ProgressStatus.COMPLETED.value,
            grade=85.0,
        ))
        self.sandbox.rollback_progress("test_sb")
        state = self.sandbox.get_sandbox_state("course_sb")
        self.assertNotIn("final_sb", state.get("available_elements", []))


if __name__ == "__main__":
    unittest.main()
