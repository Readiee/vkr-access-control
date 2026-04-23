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
from services.integration_service import IntegrationService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402
from services.policy_service import PolicyService  # noqa: E402
from services.progress_service import ProgressService  # noqa: E402
from services.sandbox_service import SandboxService  # noqa: E402


class SandboxSmokeTests(unittest.TestCase):
    def setUp(self):
        from tests._factory import make_temp_onto_copy
        self.test_owl = make_temp_onto_copy(prefix="vkr_sandbox_smoke_")
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
        self.progress_service = ProgressService(self.core, reasoner=self.reasoner, rollup=self.rollup, access=self.access)
        self.sandbox = SandboxService(self.core, reasoner=self.reasoner, access=self.access, progress=self.progress_service)

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
        self.integration_service.sync_course_structure(
            "course_sb",
            CourseSyncPayload(course_name="Sandbox smoke", elements=elements),
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

    def test_set_group_unlocks_group_restricted_element(self):
        """set_group вписывает belongs_to_group → group_restricted правило пропускает."""
        with self.core.onto:
            group = self.core.onto.Group("grp_sb_smoke")
            group.label = ["Sandbox group"]
        self.core.save()

        self.policy_service.create_policy(PolicyCreate(
            source_element_id="test_sb",
            rule_type=RuleType.GROUP,
            restricted_to_group_id="grp_sb_smoke",
            author_id="methodologist_smirnov",
        ))

        state_before = self.sandbox.get_sandbox_state("course_sb")
        self.assertIsNone(state_before.get("group_id"))
        self.assertNotIn("test_sb", state_before.get("available_elements", []))

        self.sandbox.set_group("grp_sb_smoke")
        state_after = self.sandbox.get_sandbox_state("course_sb")
        self.assertEqual(state_after.get("group_id"), "grp_sb_smoke")
        self.assertIn("test_sb", state_after.get("available_elements", []))

        self.sandbox.set_group(None)
        state_reset = self.sandbox.get_sandbox_state("course_sb")
        self.assertIsNone(state_reset.get("group_id"))
        self.assertNotIn("test_sb", state_reset.get("available_elements", []))


if __name__ == "__main__":
    unittest.main()
