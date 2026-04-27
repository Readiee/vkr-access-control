"""Unit-тесты GraphValidator: типозависимые дуги, self-reference, find_all_cycles."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config import DEFAULT_ONTOLOGY_PATH  
from owlready2 import World  

from core.enums import RuleType  
from services.graph_validator import GraphValidator, ProbePolicy  


class GraphValidatorTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self._created: list[str] = []
        with self.onto:
            self._mod_a = self.onto.Module(self._track("mod_gv_a"))
            self._mod_b = self.onto.Module(self._track("mod_gv_b"))
            self._mod_c = self.onto.Module(self._track("mod_gv_c"))
            self._mod_a.is_mandatory = True
            self._mod_b.is_mandatory = True
            self._mod_c.is_mandatory = True

    def tearDown(self):
        self.world.close()

    def _track(self, name: str) -> str:
        self._created.append(name)
        return name

    def test_completion_probe_on_self_raises_cycle(self):
        probe = ProbePolicy(
            rule_type=RuleType.COMPLETION.value,
            source_id="mod_gv_a",
            target_element_id="mod_gv_a",
        )
        path = GraphValidator.check_for_cycles(self.onto, "mod_gv_a", probe=probe)
        self.assertTrue(path, "self-reference должен давать цикл через интра-элементную дугу")

    def test_date_restricted_probe_no_edges(self):
        probe = ProbePolicy(rule_type=RuleType.DATE.value, source_id="mod_gv_a")
        path = GraphValidator.check_for_cycles(self.onto, "mod_gv_a", probe=probe)
        self.assertEqual(path, [])

    def test_group_restricted_probe_no_edges(self):
        probe = ProbePolicy(rule_type=RuleType.GROUP.value, source_id="mod_gv_a")
        path = GraphValidator.check_for_cycles(self.onto, "mod_gv_a", probe=probe)
        self.assertEqual(path, [])

    def test_viewed_required_produces_access_to_access_edge(self):
        """viewed_required даёт tgt.access → src.access, а не tgt.complete → src.access"""
        graph = GraphValidator.build_dependency_graph(self.onto)
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("policy_gv_viewed"))
            policy.rule_type = "viewed_required"
            policy.is_active = True
            policy.targets_element = self._mod_a
            self._mod_b.has_access_policy.append(policy)
        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertTrue(graph.has_edge("mod_gv_a_access", "mod_gv_b_access"))
        self.assertFalse(graph.has_edge("mod_gv_a_complete", "mod_gv_b_access"))

    def test_viewed_required_does_not_create_false_cycle_between_siblings(self):
        """viewed policy между соседями не создаёт ложный цикл: access→access ациклично."""
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("policy_gv_viewed_2"))
            policy.rule_type = "viewed_required"
            policy.is_active = True
            policy.targets_element = self._mod_a
            self._mod_b.has_access_policy.append(policy)
        self.assertEqual(GraphValidator.find_all_cycles(self.onto), [])

    def test_competency_required_expands_through_assesses(self):
        """Политика на competency превращается в дуги от всех оценивающих её элементов."""
        with self.onto:
            comp = self.onto.Competency(self._track("comp_gv_test"))
            self._mod_a.assesses = [comp]
            policy = self.onto.AccessPolicy(self._track("policy_gv_comp"))
            policy.rule_type = "competency_required"
            policy.is_active = True
            policy.targets_competency = [comp]
            self._mod_b.has_access_policy.append(policy)
        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertTrue(graph.has_edge("mod_gv_a_complete", "mod_gv_b_access"))

    def test_competency_required_walks_subcompetencies(self):
        """Если политика требует parent-comp, а оценивается sub-comp, дуга тоже строится."""
        with self.onto:
            parent_comp = self.onto.Competency(self._track("comp_gv_parent"))
            sub_comp = self.onto.Competency(self._track("comp_gv_sub"))
            sub_comp.is_subcompetency_of = [parent_comp]
            self._mod_a.assesses = [sub_comp]
            policy = self.onto.AccessPolicy(self._track("policy_gv_comp_parent"))
            policy.rule_type = "competency_required"
            policy.is_active = True
            policy.targets_competency = [parent_comp]
            self._mod_b.has_access_policy.append(policy)
        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertTrue(graph.has_edge("mod_gv_a_complete", "mod_gv_b_access"))

    def test_competency_probe_detects_cycle_through_subcompetency(self):
        """Probe-детектор должен видеть тот же цикл, что и верификация:
        если мы вешаем competency_required: parent-comp на элемент, потомок
        которого оценивает sub-comp → transitively parent-comp → цикл через
        иерархию элемента + assessor."""
        with self.onto:
            parent_comp = self.onto.Competency(self._track("comp_probe_parent"))
            sub_comp = self.onto.Competency(self._track("comp_probe_sub"))
            sub_comp.is_subcompetency_of = [parent_comp]
            # quiz внутри mod_a оценивает sub-comp → т.е. даёт parent-comp тоже
            quiz_in_a = self.onto.Test(self._track("quiz_probe_in_a"))
            quiz_in_a.assesses = [sub_comp]
            self._mod_a.contains_activity = [quiz_in_a]

        # Пробуем повесить competency_required на parent на mod_a (корень поддерева)
        probe = ProbePolicy(
            rule_type=RuleType.COMPETENCY.value,
            source_id="mod_gv_a",
            target_competency_id="comp_probe_parent",
        )
        path = GraphValidator.check_for_cycles(self.onto, "mod_gv_a", probe=probe)
        self.assertTrue(
            path,
            "Probe должен детектировать цикл mod_a → quiz_in_a → mod_a через subcompetency",
        )

    def test_and_combination_recurses_into_subpolicies(self):
        with self.onto:
            sub1 = self.onto.AccessPolicy(self._track("policy_gv_and_sub1"))
            sub1.rule_type = "completion_required"
            sub1.is_active = True
            sub1.targets_element = self._mod_a
            sub2 = self.onto.AccessPolicy(self._track("policy_gv_and_sub2"))
            sub2.rule_type = "completion_required"
            sub2.is_active = True
            sub2.targets_element = self._mod_c

            composite = self.onto.AccessPolicy(self._track("policy_gv_and"))
            composite.rule_type = "and_combination"
            composite.is_active = True
            composite.has_subpolicy = [sub1, sub2]
            self._mod_b.has_access_policy.append(composite)

        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertTrue(graph.has_edge("mod_gv_a_complete", "mod_gv_b_access"))
        self.assertTrue(graph.has_edge("mod_gv_c_complete", "mod_gv_b_access"))

    def test_or_combination_recurses_into_subpolicies(self):
        with self.onto:
            sub1 = self.onto.AccessPolicy(self._track("policy_gv_or_sub1"))
            sub1.rule_type = "viewed_required"
            sub1.is_active = True
            sub1.targets_element = self._mod_a
            sub2 = self.onto.AccessPolicy(self._track("policy_gv_or_sub2"))
            sub2.rule_type = "grade_required"
            sub2.is_active = True
            sub2.passing_threshold = 50.0
            sub2.targets_element = self._mod_c

            composite = self.onto.AccessPolicy(self._track("policy_gv_or"))
            composite.rule_type = "or_combination"
            composite.is_active = True
            composite.has_subpolicy = [sub1, sub2]
            self._mod_b.has_access_policy.append(composite)

        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertTrue(graph.has_edge("mod_gv_a_access", "mod_gv_b_access"))       # viewed
        self.assertTrue(graph.has_edge("mod_gv_c_complete", "mod_gv_b_access"))     # grade

    def test_aggregate_required_adds_edges_from_elements(self):
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("policy_gv_agg"))
            policy.rule_type = "aggregate_required"
            policy.is_active = True
            policy.aggregate_function = "AVG"
            policy.passing_threshold = 70.0
            policy.aggregate_elements = [self._mod_a, self._mod_c]
            self._mod_b.has_access_policy.append(policy)

        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertTrue(graph.has_edge("mod_gv_a_complete", "mod_gv_b_access"))
        self.assertTrue(graph.has_edge("mod_gv_c_complete", "mod_gv_b_access"))

    def test_inactive_policy_does_not_add_edges(self):
        with self.onto:
            policy = self.onto.AccessPolicy(self._track("policy_gv_inactive"))
            policy.rule_type = "completion_required"
            policy.is_active = False
            policy.targets_element = self._mod_a
            self._mod_b.has_access_policy.append(policy)

        graph = GraphValidator.build_dependency_graph(self.onto)
        self.assertFalse(graph.has_edge("mod_gv_a_complete", "mod_gv_b_access"))

    def test_recursion_guard_on_circular_subpolicies(self):
        """Циклическая композиция has_subpolicy должна отлавливаться по глубине."""
        with self.onto:
            p1 = self.onto.AccessPolicy(self._track("policy_gv_rec_1"))
            p2 = self.onto.AccessPolicy(self._track("policy_gv_rec_2"))
            p1.rule_type = "and_combination"
            p1.is_active = True
            p2.rule_type = "and_combination"
            p2.is_active = True
            p1.has_subpolicy = [p2]
            p2.has_subpolicy = [p1]
            self._mod_b.has_access_policy.append(p1)

        with self.assertRaises(RuntimeError):
            GraphValidator.build_dependency_graph(self.onto)

    def test_find_all_cycles_detects_real_cycle(self):
        with self.onto:
            p_ab = self.onto.AccessPolicy(self._track("policy_gv_cycle_ab"))
            p_ab.rule_type = "completion_required"
            p_ab.is_active = True
            p_ab.targets_element = self._mod_b
            self._mod_a.has_access_policy.append(p_ab)

            p_ba = self.onto.AccessPolicy(self._track("policy_gv_cycle_ba"))
            p_ba.rule_type = "completion_required"
            p_ba.is_active = True
            p_ba.targets_element = self._mod_a
            self._mod_b.has_access_policy.append(p_ba)

        cycles = GraphValidator.find_all_cycles(self.onto)
        nodes = {n for cycle in cycles for n in cycle}
        self.assertIn("mod_gv_a", nodes)
        self.assertIn("mod_gv_b", nodes)

    def test_find_all_cycles_clean_graph(self):
        self.assertEqual(GraphValidator.find_all_cycles(self.onto), [])


if __name__ == "__main__":
    unittest.main()
