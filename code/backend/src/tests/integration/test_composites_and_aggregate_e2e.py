"""Integration: AND/OR/aggregate_required через реальный Pellet + двухуровневую SWRL."""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  # noqa: E402

from core.enums import ElementType, RuleType  # noqa: E402
from schemas.schemas import (  # noqa: E402
    AggregateFunction,
    CourseElement,
    CourseSyncPayload,
    PolicyCreate,
)
from services.integration_service import IntegrationService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402
from services.policy_service import PolicyService  # noqa: E402


class CompositeAndAggregateEndToEndTests(unittest.TestCase):
    """Each test gets a fresh World — Pellet видит только свои индивиды."""

    def setUp(self):
        from tests._factory import make_temp_onto_copy
        self.test_owl = make_temp_onto_copy(prefix="vkr_composite_agg_")
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

        elements = [
            CourseElement(
                element_id="mod_cmp",
                name="Composite module",
                element_type=ElementType.MODULE,
                parent_id="course_cmp",
            ),
            CourseElement(
                element_id="quiz_a",
                name="Quiz A",
                element_type=ElementType.TEST,
                parent_id="mod_cmp",
            ),
            CourseElement(
                element_id="quiz_b",
                name="Quiz B",
                element_type=ElementType.TEST,
                parent_id="mod_cmp",
            ),
            CourseElement(
                element_id="final_cmp",
                name="Final",
                element_type=ElementType.TEST,
                parent_id="mod_cmp",
            ),
            CourseElement(
                element_id="target_cmp",
                name="Target",
                element_type=ElementType.LECTURE,
                parent_id="mod_cmp",
            ),
        ]
        self.integration_service.sync_course_structure(
            "course_cmp",
            CourseSyncPayload(course_name="Composite+Aggregate course", elements=elements),
        )

    def tearDown(self):
        self.world.close()
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    def _create_policy(self, **kwargs) -> dict:
        payload = PolicyCreate(author_id="methodologist_smirnov", **kwargs)
        return self.policy_service.create_policy(payload)

    # --- AND composite ---------------------------------------------------

    def test_and_combination_satisfies_when_both_subs_met(self):
        """AND композит: оба sub-условия выполнены → satisfies → is_available_for."""
        sub_a = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_a",
        )
        sub_b = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_b",
        )
        composite = self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.AND,
            subpolicy_ids=[sub_a["id"], sub_b["id"]],
        )

        with self.core.onto:
            student = self.core.onto.Student("student_cmp_and")
            quiz_a = self.core.onto.search_one(iri="*quiz_a")
            quiz_b = self.core.onto.search_one(iri="*quiz_b")

            pr_a = self.core.onto.ProgressRecord("pr_cmp_and_a")
            pr_a.refers_to_element = quiz_a
            pr_a.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_a)

            pr_b = self.core.onto.ProgressRecord("pr_cmp_and_b")
            pr_b.refers_to_element = quiz_b
            pr_b.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_b)
        self.core.save()

        result = self.reasoner.reason()
        self.assertEqual(result.status, "ok")

        target = self.core.onto.search_one(iri="*target_cmp")
        composite_node = self.core.onto.search_one(iri=f"*{composite['id']}")
        self.assertIn(composite_node, getattr(student, "satisfies", []) or [])
        self.assertIn(student, getattr(target, "is_available_for", []) or [])

    def test_and_combination_denies_when_one_sub_missing(self):
        """AND: один sub не выполнен → satisfies не выводится."""
        sub_a = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_a",
        )
        sub_b = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_b",
        )
        self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.AND,
            subpolicy_ids=[sub_a["id"], sub_b["id"]],
        )

        with self.core.onto:
            student = self.core.onto.Student("student_cmp_and_partial")
            quiz_a = self.core.onto.search_one(iri="*quiz_a")
            pr_a = self.core.onto.ProgressRecord("pr_cmp_and_partial_a")
            pr_a.refers_to_element = quiz_a
            pr_a.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_a)
            # quiz_b намеренно пропущен
        self.core.save()

        self.reasoner.reason()
        target = self.core.onto.search_one(iri="*target_cmp")
        self.assertNotIn(student, getattr(target, "is_available_for", []) or [])

    # --- OR composite ----------------------------------------------------

    def test_or_combination_satisfies_when_one_branch_met(self):
        """OR: достаточно одной sub-политики."""
        sub_a = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_a",
        )
        sub_b = self._create_policy(
            rule_type=RuleType.GRADE,
            target_element_id="quiz_b",
            passing_threshold=90.0,
        )
        self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.OR,
            subpolicy_ids=[sub_a["id"], sub_b["id"]],
        )

        with self.core.onto:
            student = self.core.onto.Student("student_cmp_or")
            quiz_a = self.core.onto.search_one(iri="*quiz_a")
            pr_a = self.core.onto.ProgressRecord("pr_cmp_or_a")
            pr_a.refers_to_element = quiz_a
            pr_a.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_a)
        self.core.save()

        self.reasoner.reason()
        target = self.core.onto.search_one(iri="*target_cmp")
        self.assertIn(student, getattr(target, "is_available_for", []) or [])

    def test_or_combination_denies_when_no_branch_met(self):
        """OR: ни одна sub-политика не сработала."""
        sub_a = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_a",
        )
        sub_b = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_b",
        )
        self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.OR,
            subpolicy_ids=[sub_a["id"], sub_b["id"]],
        )

        with self.core.onto:
            student = self.core.onto.Student("student_cmp_or_empty")
            # никакого прогресса
        self.core.save()

        self.reasoner.reason()
        target = self.core.onto.search_one(iri="*target_cmp")
        self.assertNotIn(student, getattr(target, "is_available_for", []) or [])

    # --- aggregate_required ----------------------------------------------

    def test_aggregate_avg_meets_threshold(self):
        """aggregate_required: AVG оценок ≥ threshold → satisfies."""
        self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.AGGREGATE,
            aggregate_function=AggregateFunction.AVG,
            aggregate_element_ids=["quiz_a", "quiz_b"],
            passing_threshold=70.0,
        )

        with self.core.onto:
            student = self.core.onto.Student("student_agg_pass")
            quiz_a = self.core.onto.search_one(iri="*quiz_a")
            quiz_b = self.core.onto.search_one(iri="*quiz_b")

            pr_a = self.core.onto.ProgressRecord("pr_agg_a")
            pr_a.refers_to_element = quiz_a
            pr_a.has_grade = 80.0
            pr_a.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_a)

            pr_b = self.core.onto.ProgressRecord("pr_agg_b")
            pr_b.refers_to_element = quiz_b
            pr_b.has_grade = 70.0
            pr_b.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_b)
        self.core.save()

        result = self.reasoner.reason()
        self.assertEqual(result.status, "ok")
        self.assertGreaterEqual(result.aggregate_facts, 1)

        target = self.core.onto.search_one(iri="*target_cmp")
        self.assertIn(student, getattr(target, "is_available_for", []) or [])

    def test_aggregate_avg_below_threshold_denies(self):
        """aggregate_required: AVG ниже threshold → satisfies не выводится."""
        self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.AGGREGATE,
            aggregate_function=AggregateFunction.AVG,
            aggregate_element_ids=["quiz_a", "quiz_b"],
            passing_threshold=80.0,
        )

        with self.core.onto:
            student = self.core.onto.Student("student_agg_fail")
            quiz_a = self.core.onto.search_one(iri="*quiz_a")
            quiz_b = self.core.onto.search_one(iri="*quiz_b")

            pr_a = self.core.onto.ProgressRecord("pr_agg_fail_a")
            pr_a.refers_to_element = quiz_a
            pr_a.has_grade = 60.0
            pr_a.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_a)

            pr_b = self.core.onto.ProgressRecord("pr_agg_fail_b")
            pr_b.refers_to_element = quiz_b
            pr_b.has_grade = 70.0
            pr_b.has_status = self.core.onto.status_completed
            student.has_progress_record.append(pr_b)
        self.core.save()

        self.reasoner.reason()
        target = self.core.onto.search_one(iri="*target_cmp")
        self.assertNotIn(student, getattr(target, "is_available_for", []) or [])

    # --- валидация композита/агрегата через PolicyCreate -----------------

    def test_and_combination_requires_two_unique_subs(self):
        with self.assertRaises(ValueError):
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AND,
                subpolicy_ids=["p_x"],
                author_id="methodologist_smirnov",
            )
        with self.assertRaises(ValueError):
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AND,
                subpolicy_ids=["p_x", "p_x"],
                author_id="methodologist_smirnov",
            )

    def test_and_combination_rejects_more_than_three_subs(self):
        """SWRL-шаблоны покрывают только арности 2 и 3; 4+ подполитик не выведется."""
        with self.assertRaises(ValueError) as ctx:
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AND,
                subpolicy_ids=["p1", "p2", "p3", "p4"],
                author_id="methodologist_smirnov",
            )
        self.assertIn("максимум 3", str(ctx.exception))

    def test_and_combination_accepts_exactly_three_subs(self):
        PolicyCreate(
            source_element_id="target_cmp",
            rule_type=RuleType.AND,
            subpolicy_ids=["p1", "p2", "p3"],
            author_id="methodologist_smirnov",
        )

    def test_or_combination_allows_more_than_three_subs(self):
        """Для OR верхнего предела нет — шаблон 7 унарный по sub."""
        PolicyCreate(
            source_element_id="target_cmp",
            rule_type=RuleType.OR,
            subpolicy_ids=["p1", "p2", "p3", "p4", "p5"],
            author_id="methodologist_smirnov",
        )

    def test_date_restricted_rejects_non_whole_hour(self):
        """valid_from/valid_until должны быть на целом часе (минуты/секунды = 0)."""
        with self.assertRaises(ValueError) as ctx:
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.DATE,
                valid_from=datetime(2026, 5, 1, 10, 30, 0),
                valid_until=datetime(2026, 5, 1, 18, 0, 0),
                author_id="methodologist_smirnov",
            )
        self.assertIn("целый час", str(ctx.exception))

        with self.assertRaises(ValueError):
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.DATE,
                valid_from=datetime(2026, 5, 1, 10, 0, 0),
                valid_until=datetime(2026, 5, 1, 18, 0, 15),
                author_id="methodologist_smirnov",
            )

    def test_date_restricted_accepts_whole_hour(self):
        PolicyCreate(
            source_element_id="target_cmp",
            rule_type=RuleType.DATE,
            valid_from=datetime(2026, 5, 1, 10, 0, 0),
            valid_until=datetime(2026, 5, 1, 18, 0, 0),
            author_id="methodologist_smirnov",
        )

    def test_aggregate_requires_function_and_elements(self):
        with self.assertRaises(ValueError):
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AGGREGATE,
                passing_threshold=70.0,
                aggregate_element_ids=["quiz_a"],
                # aggregate_function не задан
                author_id="methodologist_smirnov",
            )
        with self.assertRaises(ValueError):
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AGGREGATE,
                passing_threshold=70.0,
                aggregate_function=AggregateFunction.AVG,
                # aggregate_element_ids пуст
                author_id="methodologist_smirnov",
            )


    # --- Update composite через nested_subpolicies --------------------------

    def test_update_and_with_nested_replaces_old_subs(self):
        """При update AND с nested_subpolicies старые nested-подусловия удаляются,
        новые создаются и висят в has_subpolicy."""
        composite = self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.AND,
            nested_subpolicies=[
                PolicyCreate(
                    rule_type=RuleType.COMPLETION,
                    target_element_id="quiz_a",
                    author_id="methodologist_smirnov",
                ),
                PolicyCreate(
                    rule_type=RuleType.COMPLETION,
                    target_element_id="quiz_b",
                    author_id="methodologist_smirnov",
                ),
            ],
        )

        old_sub_ids = set(composite["subpolicy_ids"] or [])
        self.assertEqual(len(old_sub_ids), 2)

        # subpolicies_detail должен приходить сразу после create — иначе
        # фронт показывает «2 подусловий» вместо имён правил и не может
        # открыть composite в editor с заполненными целевыми элементами.
        details = composite.get("subpolicies_detail") or []
        self.assertEqual(len(details), 2)
        self.assertTrue(all("name" in d and d["name"] for d in details))
        self.assertEqual(
            {d["target_element_id"] for d in details},
            {"quiz_a", "quiz_b"},
        )

        updated = self.policy_service.update_policy(
            composite["id"],
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AND,
                nested_subpolicies=[
                    PolicyCreate(
                        rule_type=RuleType.COMPLETION,
                        target_element_id="final_cmp",
                        author_id="methodologist_smirnov",
                    ),
                    PolicyCreate(
                        rule_type=RuleType.GRADE,
                        target_element_id="quiz_a",
                        passing_threshold=70.0,
                        author_id="methodologist_smirnov",
                    ),
                ],
                author_id="methodologist_smirnov",
            ),
        )

        new_sub_ids = set(updated["subpolicy_ids"] or [])
        self.assertEqual(len(new_sub_ids), 2)
        self.assertTrue(old_sub_ids.isdisjoint(new_sub_ids))

        # Старые nested полностью удалены из ABox
        for old_id in old_sub_ids:
            self.assertIsNone(
                self.core.policies.find_by_id(old_id),
                f"Старое подусловие {old_id} должно быть удалено",
            )

    def test_update_and_preserves_external_subpolicy(self):
        """Если subpolicy привязана к элементу как самостоятельная политика,
        update композита с nested не удаляет её, даже если она была в старом наборе."""
        external = self._create_policy(
            source_element_id="final_cmp",
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_a",
        )
        nested_only = self._create_policy(
            rule_type=RuleType.COMPLETION,
            target_element_id="quiz_b",
        )

        composite = self._create_policy(
            source_element_id="target_cmp",
            rule_type=RuleType.AND,
            subpolicy_ids=[external["id"], nested_only["id"]],
        )

        self.policy_service.update_policy(
            composite["id"],
            PolicyCreate(
                source_element_id="target_cmp",
                rule_type=RuleType.AND,
                nested_subpolicies=[
                    PolicyCreate(
                        rule_type=RuleType.COMPLETION,
                        target_element_id="final_cmp",
                        author_id="methodologist_smirnov",
                    ),
                    PolicyCreate(
                        rule_type=RuleType.COMPLETION,
                        target_element_id="quiz_b",
                        author_id="methodologist_smirnov",
                    ),
                ],
                author_id="methodologist_smirnov",
            ),
        )

        self.assertIsNotNone(
            self.core.policies.find_by_id(external["id"]),
            "Политика с source_element_id не должна удаляться при update composite",
        )


if __name__ == "__main__":
    unittest.main()
