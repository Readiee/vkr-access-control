import sys
import os
import unittest

# tests/integration/ → tests/ → src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from schemas import CourseElement, PolicyCreate, ProgressEvent, CourseSyncPayload
from core.enums import ElementType, RuleType, ProgressStatus, EventType
from core.config import DEFAULT_ONTOLOGY_PATH
from core.ontology_core import OntologyCore
from services.policy_service import PolicyService
from services.integration_service import IntegrationService
from services.progress_service import ProgressService


class TestOntologyIntegration(unittest.TestCase):
    def setUp(self):
        from tests._factory import make_temp_onto_copy
        from owlready2 import World
        self.original_owl = DEFAULT_ONTOLOGY_PATH
        self.test_owl = make_temp_onto_copy(prefix="vkr_integration_")

        self.world = World()
        self.core = OntologyCore(self.test_owl, world=self.world)
        from core.cache_manager import CacheManager
        from services.reasoning import ReasoningOrchestrator
        from services.rollup_service import RollupService
        from services.access import AccessService
        from services.verification import VerificationService
        self.cache = CacheManager(None)
        self.reasoner = ReasoningOrchestrator(self.core.onto)
        self.rollup = RollupService(self.core)
        self.access = AccessService(self.core, cache=self.cache, reasoner=self.reasoner)
        self.verification = VerificationService(self.core, reasoner=self.reasoner, cache=self.cache)
        self.policy_service = PolicyService(self.core, reasoner=self.reasoner, cache=self.cache)
        self.integration_service = IntegrationService(self.core, verification=self.verification, cache=self.cache)
        self.progress_service = ProgressService(self.core, reasoner=self.reasoner, rollup=self.rollup, access=self.access)
        
        print(f"\n[CHECKPOINT 1] Ontology Core initialized: {self.test_owl}")
        
    def tearDown(self):
        self.world.close()
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)
        print("[CHECKPOINT END] Test environment cleaned up.")

    def test_full_flow_with_reasoning(self):
        print("\n--- START OF TEST FOR TREE GENERATION AND LOGICAL REASONING ---")
        
        # [1] Синхронизация структуры
        elements = [
            CourseElement(element_id="mod_1", name="Programming module", element_type=ElementType.MODULE, parent_id="course_1"),
            CourseElement(element_id="lec_intro", name="Introduction", element_type=ElementType.LECTURE, parent_id="mod_1"),
            CourseElement(element_id="test_basics", name="Basics test", element_type=ElementType.TEST, parent_id="mod_1")
        ]
        payload = CourseSyncPayload(course_name="Тестовый Курс 1", elements=elements)
        self.integration_service.sync_course_structure("course_1", payload)
        print("[CHECKPOINT 2] Course structure synchronized (3 elements).")

        # [2] Создание зависимости (лекция -> тест)
        policy = PolicyCreate(
            source_element_id="test_basics",
            rule_type=RuleType.COMPLETION,
            target_element_id="lec_intro",
            author_id="methodologist_1"
        )
        self.policy_service.create_policy(policy)
        print("[CHECKPOINT 3] Policy created: test_basics depends on completion of lec_intro.")

        # [3] Проверка дерева до начала обучения
        tree = self.integration_service.get_course_tree("course_1")
        self.assertEqual(len(tree[0]["children"]), 1, "There should be 1 module")
        print("[CHECKPOINT 4] Course tree successfully generated before training.")

        # [4] Регистрация прогресса (завершаем лекцию)
        event = ProgressEvent(
            student_id="student_ivan",
            element_id="lec_intro",
            event_type=EventType.COMPLETED
        )
        print("[CHECKPOINT 5] Progress registration: student completed lec_intro. Starting Reasoner...")
        # Метод register_progress теперь в progress_service, но он сам вызывает run_reasoner
        response = self.progress_service.register_progress(event)
        
        # [5] Проверка логического вывода
        available_ids = response["inferred_available_elements"]
        print(f"[CHECKPOINT 6] Reasoning completed. Available elements: {available_ids}")
        
        self.assertIn("test_basics", available_ids, "test_basics should be available due to logical reasoning!")
        
        student_node = self.core.onto.search_one(iri="*student_student_ivan")
        test_node = self.core.onto.search_one(iri="*test_basics")
        
        self.assertIn(student_node, test_node.is_available_for, "The 'is_available_for' relationship is not created in the graph!")
        print("[CHECKPOINT 7] GRAPH CHECK: 'is_available_for' relationship for student confirmed.")

        print("\n--- TEST PASSED: Logic and Reasoning work correctly ---")

    def test_recursive_status_rollup(self):
        """Проверяет Roll-up статуса."""
        # 1. Подготовка иерархии
        elements = [
            CourseElement(element_id="course_rollup", element_type=ElementType.COURSE, name="Rollup Course", is_mandatory=True),
            CourseElement(element_id="mod_rollup", element_type=ElementType.MODULE, name="Rollup Module", parent_id="course_rollup", is_mandatory=True),
            CourseElement(element_id="lec_req", element_type=ElementType.LECTURE, name="Required Lec", parent_id="mod_rollup", is_mandatory=True),
            CourseElement(element_id="prac_opt", element_type=ElementType.PRACTICE, name="Optional Prac", parent_id="mod_rollup", is_mandatory=False),
            CourseElement(element_id="test_req", element_type=ElementType.TEST, name="Required Test", parent_id="mod_rollup", is_mandatory=True),
        ]
        payload = CourseSyncPayload(course_name="Курс для теста Roll-up", elements=elements)
        self.integration_service.sync_course_structure("course_rollup", payload)
        student_id = "student_tester"

        def get_status(eid: str):
            el = self.core.onto.search_one(iri=f"*{eid}")
            st = self.core.onto.search_one(iri=f"*{student_id}")
            if not st or not el: 
                return None
            for r in self.core.onto.ProgressRecord.instances():
                if getattr(r, "refers_to_student", None) is st and getattr(r, "refers_to_element", None) is el:
                    status_obj = getattr(r, "has_status", None)
                    if status_obj is None:
                        return None
                    if hasattr(status_obj, "name"):
                        return status_obj.name.replace("status_", "")
                    return str(status_obj)
            return None

        # 2. Выполняем необязательную практику
        self.progress_service.update_progress(student_id, "prac_opt", ProgressStatus.COMPLETED)
        self.assertNotEqual(get_status("mod_rollup"), ProgressStatus.COMPLETED.value)

        # 3. Выполняем первую обязательную лекцию
        self.progress_service.update_progress(student_id, "lec_req", ProgressStatus.COMPLETED)
        self.assertNotEqual(get_status("mod_rollup"), ProgressStatus.COMPLETED.value)

        # 4. Выполняем последний обязательный тест
        self.progress_service.update_progress(student_id, "test_req", ProgressStatus.COMPLETED)

        # 5. Проверки
        self.assertEqual(get_status("mod_rollup"), ProgressStatus.COMPLETED.value, "Module should be completed")
        self.assertEqual(get_status("course_rollup"), ProgressStatus.COMPLETED.value, "Course should be completed (recursion)")
        print("[CHECKPOINT] Recursive Roll-up worked perfectly!")

    def test_set_element_competencies_updates_assesses_and_tree(self):
        """set_element_competencies пишет assesses и возвращает его в tree."""
        elements = [
            CourseElement(element_id="course_ec", element_type=ElementType.COURSE, name="EC Course", is_mandatory=True),
            CourseElement(element_id="mod_ec", element_type=ElementType.MODULE, name="EC Module", parent_id="course_ec", is_mandatory=True),
            CourseElement(element_id="test_ec", element_type=ElementType.TEST, name="EC Test", parent_id="mod_ec", is_mandatory=True),
        ]
        self.integration_service.sync_course_structure(
            "course_ec", CourseSyncPayload(course_name="EC", elements=elements),
        )
        with self.core.onto:
            comp_x = self.core.onto.Competency("comp_ec_x")
            comp_x.label = ["EC X"]
            comp_y = self.core.onto.Competency("comp_ec_y")
            comp_y.label = ["EC Y"]
        self.core.save()

        result = self.integration_service.set_element_competencies(
            "test_ec", ["comp_ec_x", "comp_ec_y"],
        )
        self.assertEqual({c["id"] for c in result["assesses"]}, {"comp_ec_x", "comp_ec_y"})

        tree = self.integration_service.get_course_tree("course_ec")
        test_node = tree[0]["children"][0]["children"][0]
        assesses_ids = {c["id"] for c in test_node["data"]["assesses"]}
        self.assertEqual(assesses_ids, {"comp_ec_x", "comp_ec_y"})

        # Переустановка на один элемент — старый отваливается
        self.integration_service.set_element_competencies("test_ec", ["comp_ec_x"])
        tree_after = self.integration_service.get_course_tree("course_ec")
        test_node_after = tree_after[0]["children"][0]["children"][0]
        self.assertEqual({c["id"] for c in test_node_after["data"]["assesses"]}, {"comp_ec_x"})

    def test_set_element_mandatory_toggles_flag_in_tree(self):
        elements = [
            CourseElement(element_id="course_im", element_type=ElementType.COURSE, name="IM Course", is_mandatory=True),
            CourseElement(element_id="mod_im", element_type=ElementType.MODULE, name="IM Module", parent_id="course_im", is_mandatory=True),
            CourseElement(element_id="lec_im", element_type=ElementType.LECTURE, name="IM Lec", parent_id="mod_im", is_mandatory=True),
        ]
        self.integration_service.sync_course_structure(
            "course_im", CourseSyncPayload(course_name="IM", elements=elements),
        )

        tree_before = self.integration_service.get_course_tree("course_im")
        lec_before = tree_before[0]["children"][0]["children"][0]
        self.assertTrue(lec_before["data"]["is_mandatory"])

        result = self.integration_service.set_element_mandatory("lec_im", False)
        self.assertEqual(result, {"element_id": "lec_im", "is_mandatory": False})

        tree_after = self.integration_service.get_course_tree("course_im")
        lec_after = tree_after[0]["children"][0]["children"][0]
        self.assertFalse(lec_after["data"]["is_mandatory"])

        # Возврат
        self.integration_service.set_element_mandatory("lec_im", True)
        tree_back = self.integration_service.get_course_tree("course_im")
        self.assertTrue(tree_back[0]["children"][0]["children"][0]["data"]["is_mandatory"])

    def test_set_element_mandatory_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.integration_service.set_element_mandatory("nonexistent_element", True)

    def test_set_element_competencies_unknown_raises(self):
        elements = [
            CourseElement(element_id="course_ec2", element_type=ElementType.COURSE, name="EC2", is_mandatory=True),
            CourseElement(element_id="test_ec2", element_type=ElementType.TEST, name="EC2 Test", parent_id="course_ec2", is_mandatory=True),
        ]
        self.integration_service.sync_course_structure(
            "course_ec2", CourseSyncPayload(course_name="EC2", elements=elements),
        )
        with self.assertRaises(ValueError):
            self.integration_service.set_element_competencies("test_ec2", ["nonexistent_comp"])
        with self.assertRaises(ValueError):
            self.integration_service.set_element_competencies("nonexistent_element", [])


if __name__ == '__main__':
    unittest.main()
