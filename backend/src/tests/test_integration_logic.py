import sys
import os
import unittest
import shutil
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.schemas import CourseElement, PolicyCreate, ProgressEvent, CourseSyncPayload
from core.enums import ElementType, RuleType, ProgressStatus, EventType
from services.ontology_core import OntologyCore
from services.policy_service import PolicyService
from services.course_service import CourseService
from services.progress_service import ProgressService

class TestOntologyIntegration(unittest.TestCase):
    def setUp(self):
        self.original_owl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "edu_ontology_with_rules.owl")
        self.test_owl = "test_integration.owl"
        shutil.copy(self.original_owl, self.test_owl)
        
        self.core = OntologyCore(self.test_owl)
        self.policy_service = PolicyService(self.core)
        self.course_service = CourseService(self.core)
        self.progress_service = ProgressService(self.core)
        
        print(f"\n[CHECKPOINT 1] Ontology Core initialized: {self.test_owl}")
        
    def tearDown(self):
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
        self.course_service.sync_course_structure("course_1", payload)
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
        tree = self.course_service.get_course_tree("course_1")
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
            CourseElement(element_id="course_rollup", element_type=ElementType.COURSE, name="Rollup Course", is_required=True),
            CourseElement(element_id="mod_rollup", element_type=ElementType.MODULE, name="Rollup Module", parent_id="course_rollup", is_required=True),
            CourseElement(element_id="lec_req", element_type=ElementType.LECTURE, name="Required Lec", parent_id="mod_rollup", is_required=True),
            CourseElement(element_id="prac_opt", element_type=ElementType.PRACTICE, name="Optional Prac", parent_id="mod_rollup", is_required=False),
            CourseElement(element_id="test_req", element_type=ElementType.TEST, name="Required Test", parent_id="mod_rollup", is_required=True),
        ]
        payload = CourseSyncPayload(course_name="Курс для теста Roll-up", elements=elements)
        self.course_service.sync_course_structure("course_rollup", payload)
        student_id = "student_tester"

        def get_status(eid: str):
            el = self.core.onto.search_one(iri=f"*{eid}")
            st = self.core.onto.search_one(iri=f"*{student_id}")
            if not st or not el: 
                return None
            for r in self.core.onto.ProgressRecord.instances():
                if st in getattr(r, "refers_to_student", []) and el in getattr(r, "refers_to_element", []):
                    has_status = getattr(r, "has_status", [])
                    if not has_status: return None
                    status_obj = has_status[0]
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

if __name__ == '__main__':
    unittest.main()
