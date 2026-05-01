"""Прогон VerificationService по всем сценариям из code/onto/scenarios/

Каждый сценарий — готовый .owl-файл и запись в scenarios_ground_truth.json
с ожидаемым verdict по СВ-1..СВ-5. Тесты сверяют статусы каждого свойства;
отдельно проверяют наличие violation с ожидаемыми полями (policy_id,
policies, elements, dominant/dominated)

Этот же набор используется как fixture для экспериментов фазы 3
"""
from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World  

from core.cache_manager import CacheManager  
from core.ontology_core import OntologyCore  
from services.reasoning import ReasoningOrchestrator  
from services.verification import VerificationService  

SCENARIOS_OWL_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "onto", "ontologies", "scenarios"
    )
)
GROUND_TRUTH_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "scenarios_ground_truth.json")
)


def _load_ground_truth():
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["scenarios"]


def _load_scenario(name: str):
    owl_path = os.path.join(SCENARIOS_OWL_DIR, f"{name}.owl")
    world = World()
    onto = world.get_ontology(f"file://{owl_path.replace(os.sep, '/')}").load()
    core = OntologyCore(onto_path=owl_path, world=world)
    # OntologyCore.__init__ сам загрузит — подменяем на уже открытый onto/world,
    # чтобы не держать две копии с конфликтующим reasoning state.
    core.onto = onto
    core.world = world
    return core


class VerificationScenariosTests(unittest.TestCase):
    """Один test-метод на сценарий — удобно при падении видеть сразу, какой сломан."""

    @classmethod
    def setUpClass(cls):
        cls.ground_truth = _load_ground_truth()

    def _run(self, name: str):
        spec = next(s for s in self.ground_truth if s["name"] == name)
        core = _load_scenario(name)
        reasoner = ReasoningOrchestrator(core.onto)
        cache = CacheManager(None)
        service = VerificationService(core, reasoner=reasoner, cache=cache)
        report = service.verify(spec["course_id"], include_subsumption=spec.get("full", False))
        return spec, report

    def _assert_property(self, report, prop: str, expected_status: str):
        actual = report.properties.get(prop)
        self.assertIsNotNone(actual, f"Свойство {prop} отсутствует в отчёте")
        self.assertEqual(
            actual.status, expected_status,
            f"{prop}: ожидалось {expected_status}, получено {actual.status}, violations={actual.violations}"
        )

    def test_happy_path_all_properties_pass(self):
        spec, report = self._run("happy_path")
        for prop, expected in spec["expected"].items():
            if isinstance(expected, str):
                self._assert_property(report, prop, expected)

    def test_bad_sv1_consistency_failed(self):
        spec, report = self._run("bad_sv1_disjointness")
        self._assert_property(report, "consistency", "failed")
        codes = {v["code"] for v in report.properties["consistency"].violations}
        self.assertIn("SV1_INCONSISTENT", codes)

    def test_bad_sv2_acyclicity_failed_with_policies(self):
        spec, report = self._run("bad_sv2_cycle")
        self._assert_property(report, "acyclicity", "failed")
        cycles = report.properties["acyclicity"].violations
        self.assertTrue(cycles, "Ожидался хотя бы один цикл")
        all_policies = {p for c in cycles for p in (c.get("policies") or [])}
        self.assertTrue(all_policies & {"p_cycle_ab", "p_cycle_ba"})

    def test_bad_sv3_atomic_threshold_unsat(self):
        spec, report = self._run("bad_sv3_atomic_threshold")
        self._assert_property(report, "reachability", "failed")
        reasons = {v["code"] for v in report.properties["reachability"].violations}
        self.assertIn("SV3_ATOMIC_UNSAT", reasons)
        policies = {v.get("policy_id") for v in report.properties["reachability"].violations}
        self.assertIn("p_unreach_threshold", policies)

    def test_bad_sv3_empty_date_unsat(self):
        spec, report = self._run("bad_sv3_empty_date")
        self._assert_property(report, "reachability", "failed")
        policies = {v.get("policy_id") for v in report.properties["reachability"].violations}
        self.assertIn("p_unreach_date", policies)

    def test_bad_sv3_structural_unreachable_elements(self):
        spec, report = self._run("bad_sv3_structural")
        self._assert_property(report, "reachability", "failed")
        elements = {v.get("element_id") for v in report.properties["reachability"].violations}
        self.assertTrue({"elem_a", "elem_b", "elem_c"} & elements)

    def test_bad_sv4_redundant_reports_weak_dominates_strong(self):
        spec, report = self._run("bad_sv4_redundant")
        self._assert_property(report, "redundancy", "failed")
        pairs = [(v.get("dominant"), v.get("dominated"))
                 for v in report.properties["redundancy"].violations]
        self.assertIn(("p_red_weak", "p_red_strong"), pairs)

    def test_bad_sv5_subject_subsumption_detected(self):
        spec, report = self._run("bad_sv5_subject")
        self._assert_property(report, "subsumption", "failed")
        dominated = {v.get("dominated") for v in report.properties["subsumption"].violations}
        self.assertIn("p_subj_group", dominated)


if __name__ == "__main__":
    unittest.main()
