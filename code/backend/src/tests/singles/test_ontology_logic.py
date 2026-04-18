import sys
import os
import unittest
from datetime import datetime

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import CourseElement, ElementType, PolicyCreate, RuleType
from ontology_service import OntologyService

import shutil

class TestOntologyService(unittest.TestCase):
    def setUp(self):
        self.original_owl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "edu_ontology_with_rules.owl")
        self.test_owl = "test_edu_ontology.owl" # Current working directory
        shutil.copy(self.original_owl, self.test_owl)
        self.service = OntologyService(self.test_owl)
        
    def tearDown(self):
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)
            
    def test_sync_and_tree(self):
        # 1. Sync a test course
        elements = [
            CourseElement(element_id="test_module_1", name="Тестовый модуль 1", element_type=ElementType.MODULE, parent_id="test_course_1"),
            CourseElement(element_id="test_lecture_1", name="Тестовая лекция 1", element_type=ElementType.LECTURE, parent_id="test_module_1"),
            CourseElement(element_id="test_test_1", name="Тестовое задание 1", element_type=ElementType.TEST, parent_id="test_module_1")
        ]
        
        # Test creating course elements
        result = self.service.sync_course_structure("test_course_1", elements)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["synced_elements_count"], 3)
        
        # We need to manually add label to course if it wasn't specified in sync elements
        course = self.service._get_or_create_element("test_course_1", self.service.onto.Course)
        course.label = ["Курс Тестовый"]
        
        # 2. Add a policy
        policy = PolicyCreate(
            source_element_id="test_lecture_1",
            rule_type=RuleType.VIEWED,
            author_id="test_author_1"
        )
        created_policy = self.service.create_policy(policy)
        
        self.assertIn("id", created_policy)
        
        # 3. Retrieve tree
        tree = self.service.get_course_tree("test_course_1")
        
        # Verify structure
        self.assertEqual(len(tree), 1)
        root = tree[0]
        self.assertEqual(root["key"], "test_course_1")
        self.assertEqual(root["data"]["name"], "Курс Тестовый")
        
        children = root.get("children", [])
        self.assertEqual(len(children), 1)
        
        module = children[0]
        self.assertEqual(module["key"], "test_module_1")
        self.assertEqual(module["data"]["name"], "Тестовый модуль 1")
        
        module_children = module.get("children", [])
        self.assertEqual(len(module_children), 2)
        
        # Verify policy is attached
        lecture = next(c for c in module_children if c["key"] == "test_lecture_1")
        self.assertEqual(lecture["data"]["name"], "Тестовая лекция 1")
        
        policies = lecture["data"].get("policies", [])
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0]["source_element_id"], "test_lecture_1")
        self.assertEqual(policies[0]["rule_type"], "viewed_required")

if __name__ == '__main__':
    unittest.main()
