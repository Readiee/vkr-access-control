"""Unit-тесты PolicyService: rollback toggle/update при inconsistent reason

Reasoner мокается стабом, Pellet здесь не нужен. Проверяется поведение
PolicyService на путях, где reason() возвращает не «ok»: тип сохранённого
is_active, целостность has_subpolicy при rollback update_policy
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World

from core.enums import RuleType
from schemas.schemas import PolicyCreate
from services.cache_manager import CacheManager
from services.ontology_core import OntologyCore
from services.policy_service import PolicyConflictError, PolicyService
from services.reasoning.orchestrator import ReasoningResult
from tests._factory import make_temp_onto_copy


class _ScriptedReasoner:
    """Reasoner с очередью статусов; пустая очередь → «ok»

    queue_status дописывает статусы в порядке будущих вызовов reason().
    Поведение нужно, чтобы прогнать setup-сценарий на «ok» по умолчанию,
    а в нужный момент инжектировать «inconsistent» точно в N-й вызов
    """

    def __init__(self) -> None:
        self.queue: List[str] = []
        self.calls = 0

    def queue_status(self, *statuses: str) -> None:
        self.queue.extend(statuses)

    def reason(self) -> ReasoningResult:
        self.calls += 1
        status = self.queue.pop(0) if self.queue else "ok"
        return ReasoningResult(
            status=status,
            error="mocked-inconsistency" if status != "ok" else None,
        )


class PolicyServiceRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_owl = make_temp_onto_copy(prefix="vkr_policy_rollback_")
        self.world = World()
        self.core = OntologyCore(self.test_owl, world=self.world)
        self.cache = CacheManager(None)
        self.reasoner = _ScriptedReasoner()
        self.service = PolicyService(self.core, reasoner=self.reasoner, cache=self.cache)

        with self.core.onto:
            self.course = self.core.onto.Course("course_pr")
            self.lec = self.core.onto.Lecture("lec_pr_target")
            self.test_node = self.core.onto.Test("test_pr_source")
            self.course.contains_activity = [self.lec, self.test_node]
            self.methodologist = self.core.onto.Methodologist("meth_pr")

    def tearDown(self) -> None:
        self.world.close()
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    def _create_active_completion_policy(self) -> str:
        payload = PolicyCreate(
            source_element_id="test_pr_source",
            rule_type=RuleType.COMPLETION,
            target_element_id="lec_pr_target",
            author_id="meth_pr",
            is_active=True,
        )
        result = self.service.create_policy(payload)
        return result["id"]

    def test_toggle_policy_inconsistent_rollback_keeps_bool_is_active(self):
        """При inconsistent после toggle is_active восстанавливается как bool

        Старый код присваивал результат `list(...)` скалярному свойству и валил
        TypeError на is_active=True. Регрессия: rollback должен оставлять bool
        """
        policy_id = self._create_active_completion_policy()
        before = self.core.policies.find_by_id(policy_id).is_active
        self.assertIsInstance(before, bool)
        self.assertTrue(before)

        self.reasoner.queue_status("inconsistent")
        with self.assertRaises(PolicyConflictError):
            self.service.toggle_policy(policy_id, False)

        restored = self.core.policies.find_by_id(policy_id).is_active
        self.assertIsInstance(restored, bool)
        self.assertTrue(restored)

    def test_toggle_policy_success_persists_new_value_as_bool(self):
        """Happy-path: toggle с reasoner=ok меняет флаг и хранит его скаляром"""
        policy_id = self._create_active_completion_policy()
        self.service.toggle_policy(policy_id, False)

        flag = self.core.policies.find_by_id(policy_id).is_active
        self.assertIsInstance(flag, bool)
        self.assertFalse(flag)

    def test_update_policy_inconsistent_rollback_preserves_old_subpolicies(self):
        """При inconsistent после update старые has_subpolicy остаются в ABox

        Раньше cleanup осиротевших подусловий шёл до reason: rollback по
        snapshot восстанавливал ссылки на уничтоженные индивиды. Теперь cleanup
        выполняется только после успешного reason
        """
        and_payload = PolicyCreate(
            source_element_id="test_pr_source",
            rule_type=RuleType.AND,
            author_id="meth_pr",
            nested_subpolicies=[
                PolicyCreate(
                    rule_type=RuleType.COMPLETION,
                    target_element_id="lec_pr_target",
                    author_id="meth_pr",
                ),
                PolicyCreate(
                    rule_type=RuleType.GRADE,
                    target_element_id="lec_pr_target",
                    passing_threshold=60,
                    author_id="meth_pr",
                ),
            ],
        )
        and_created = self.service.create_policy(and_payload)
        and_id = and_created["id"]
        original_sub_ids = list(and_created["subpolicy_ids"])
        self.assertEqual(len(original_sub_ids), 2)

        new_payload = PolicyCreate(
            source_element_id="test_pr_source",
            rule_type=RuleType.AND,
            author_id="meth_pr",
            nested_subpolicies=[
                PolicyCreate(
                    rule_type=RuleType.COMPLETION,
                    target_element_id="lec_pr_target",
                    author_id="meth_pr",
                ),
                PolicyCreate(
                    rule_type=RuleType.VIEWED,
                    target_element_id="lec_pr_target",
                    author_id="meth_pr",
                ),
            ],
        )

        # 2 reason на свежесозданные nested, последний — inconsistent на самом update
        self.reasoner.queue_status("ok", "ok", "inconsistent")
        with self.assertRaises(PolicyConflictError):
            self.service.update_policy(and_id, new_payload)

        and_after = self.core.policies.find_by_id(and_id)
        actual_sub_ids = sorted(s.name for s in (and_after.has_subpolicy or []))
        self.assertEqual(
            actual_sub_ids,
            sorted(original_sub_ids),
            "rollback должен вернуть исходный список подусловий",
        )

        for sub_id in original_sub_ids:
            sub = self.core.policies.find_by_id(sub_id)
            self.assertIsNotNone(sub, f"подусловие {sub_id} должно существовать после rollback")
            rt = getattr(sub, "rule_type", None)
            self.assertIsNotNone(rt, f"у {sub_id} должен сохраниться rule_type после rollback")

    def test_update_policy_success_runs_cleanup_after_reason(self):
        """Happy-path: после ok-update осиротевшие подусловия удаляются"""
        and_payload = PolicyCreate(
            source_element_id="test_pr_source",
            rule_type=RuleType.AND,
            author_id="meth_pr",
            nested_subpolicies=[
                PolicyCreate(
                    rule_type=RuleType.COMPLETION,
                    target_element_id="lec_pr_target",
                    author_id="meth_pr",
                ),
                PolicyCreate(
                    rule_type=RuleType.GRADE,
                    target_element_id="lec_pr_target",
                    passing_threshold=60,
                    author_id="meth_pr",
                ),
            ],
        )
        and_created = self.service.create_policy(and_payload)
        and_id = and_created["id"]
        original_sub_ids = list(and_created["subpolicy_ids"])

        new_payload = PolicyCreate(
            source_element_id="test_pr_source",
            rule_type=RuleType.AND,
            author_id="meth_pr",
            nested_subpolicies=[
                PolicyCreate(
                    rule_type=RuleType.COMPLETION,
                    target_element_id="lec_pr_target",
                    author_id="meth_pr",
                ),
                PolicyCreate(
                    rule_type=RuleType.VIEWED,
                    target_element_id="lec_pr_target",
                    author_id="meth_pr",
                ),
            ],
        )

        updated = self.service.update_policy(and_id, new_payload)

        self.assertEqual(len(updated["subpolicy_ids"]), 2)
        for old_id in original_sub_ids:
            self.assertIsNone(
                self.core.policies.find_by_id(old_id),
                f"осиротевшее подусловие {old_id} должно быть удалено после ok-update",
            )


if __name__ == "__main__":
    unittest.main()
