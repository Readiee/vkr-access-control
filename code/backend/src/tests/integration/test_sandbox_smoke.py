"""Smoke-тест симулятора end-to-end на реальном Pellet

Покрывает три точки симулятора: сброс песочницы, симуляцию прогресса с
компетенциями, чтение состояния (доступы + прогресс)
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  

from core.enums import ElementType, RuleType, ProgressStatus  
from schemas.schemas import CourseElement, CourseSyncPayload, PolicyCreate  
from services.integration_service import IntegrationService  
from services.ontology_core import OntologyCore  
from services.policy_service import PolicyService  
from services.progress_service import ProgressService  
from services.sandbox_service import SandboxService  


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
        """Тестовый студент без прогресса → final_sb закрыт"""
        state = self.sandbox.get_sandbox_state("course_sb")
        avail = state.get("available_elements", [])
        self.assertIn("mod_sb", avail)
        self.assertIn("test_sb", avail)
        self.assertNotIn("final_sb", avail)

    def test_uc7b_simulate_progress_opens_element(self):
        """Симуляция прогресса с оценкой → SWRL выводит satisfies → final открывается"""
        self.sandbox.simulate_progress(SimpleNamespace(
            element_id="test_sb",
            status=ProgressStatus.COMPLETED.value,
            grade=85.0,
        ))
        state = self.sandbox.get_sandbox_state("course_sb")
        self.assertIn("final_sb", state.get("available_elements", []))

    def test_uc7a_reset_clears_progress(self):
        """reset удаляет прогресс — final_sb снова закрыт"""
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

    def test_h2_grants_competency_from_completed_assessor(self):
        """H-2: прохождение элемента с assesses выдаёт студенту компетенцию,
        открывая элементы, заблокированные competency_required. Rollback
        прогресса — компетенция снова исчезает."""
        with self.core.onto:
            comp = self.core.onto.Competency("comp_grant_smoke")
            comp.label = ["Grant smoke competency"]
            test_sb_el = self.core.onto.search_one(iri="*test_sb")
            test_sb_el.assesses = [comp]
        self.core.save()

        self.policy_service.create_policy(PolicyCreate(
            source_element_id="final_sb",
            rule_type=RuleType.COMPETENCY,
            target_competency_id="comp_grant_smoke",
            author_id="methodologist_smirnov",
        ))

        initial = self.sandbox.get_sandbox_state("course_sb")
        self.assertNotIn("comp_grant_smoke", initial.get("active_competencies", []))
        self.assertNotIn("final_sb", initial.get("available_elements", []))

        self.sandbox.simulate_progress(SimpleNamespace(
            element_id="test_sb",
            status=ProgressStatus.COMPLETED.value,
            grade=None,
        ))
        granted = self.sandbox.get_sandbox_state("course_sb")
        self.assertIn("comp_grant_smoke", granted.get("active_competencies", []))
        self.assertIn("final_sb", granted.get("available_elements", []))

        self.sandbox.rollback_progress("test_sb")
        rolled_back = self.sandbox.get_sandbox_state("course_sb")
        self.assertNotIn("comp_grant_smoke", rolled_back.get("active_competencies", []))
        self.assertNotIn("final_sb", rolled_back.get("available_elements", []))

    def test_set_competencies_unlocks_competency_required_element(self):
        """set_competencies прописывает has_competency → competency_required пускает.

        Регрессия: ранее компетенции искались через core.courses.find_by_id,
        который фильтрует по CourseStructure — Competency при этом не
        находился и has_competency оставался пустым, хотя сервис возвращал ok.
        """
        with self.core.onto:
            comp = self.core.onto.Competency("comp_sb_smoke")
            comp.label = ["Sandbox competency"]
        self.core.save()

        self.policy_service.create_policy(PolicyCreate(
            source_element_id="test_sb",
            rule_type=RuleType.COMPETENCY,
            target_competency_id="comp_sb_smoke",
            author_id="methodologist_smirnov",
        ))

        state_before = self.sandbox.get_sandbox_state("course_sb")
        self.assertEqual(state_before.get("active_competencies"), [])
        self.assertNotIn("test_sb", state_before.get("available_elements", []))

        self.sandbox.set_competencies(["comp_sb_smoke"])
        state_after = self.sandbox.get_sandbox_state("course_sb")
        self.assertIn("comp_sb_smoke", state_after.get("active_competencies", []))
        self.assertIn("test_sb", state_after.get("available_elements", []))

    def test_set_groups_unlocks_group_restricted_element(self):
        """set_groups вписывает belongs_to_group (множество) → group_restricted правило пропускает."""
        with self.core.onto:
            group_target = self.core.onto.Group("grp_sb_smoke")
            group_target.label = ["Sandbox group"]
            group_other = self.core.onto.Group("grp_sb_other")
            group_other.label = ["Other group"]
        self.core.save()

        self.policy_service.create_policy(PolicyCreate(
            source_element_id="test_sb",
            rule_type=RuleType.GROUP,
            restricted_to_group_id="grp_sb_smoke",
            author_id="methodologist_smirnov",
        ))

        state_before = self.sandbox.get_sandbox_state("course_sb")
        self.assertEqual(state_before.get("group_ids"), [])
        self.assertNotIn("test_sb", state_before.get("available_elements", []))

        # Несколько групп: правило group_restricted сматчит, если хотя бы одна совпадает
        self.sandbox.set_groups(["grp_sb_other", "grp_sb_smoke"])
        state_after = self.sandbox.get_sandbox_state("course_sb")
        self.assertEqual(
            sorted(state_after.get("group_ids", [])),
            sorted(["grp_sb_other", "grp_sb_smoke"]),
        )
        self.assertIn("test_sb", state_after.get("available_elements", []))

        self.sandbox.set_groups([])
        state_reset = self.sandbox.get_sandbox_state("course_sb")
        self.assertEqual(state_reset.get("group_ids"), [])
        self.assertNotIn("test_sb", state_reset.get("available_elements", []))


if __name__ == "__main__":
    unittest.main()
