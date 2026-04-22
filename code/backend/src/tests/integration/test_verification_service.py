"""Integration: VerificationService с реальным Pellet на временной онтологии."""
from __future__ import annotations

import os
import shutil
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from schemas.schemas import CourseElement, CourseSyncPayload, PolicyCreate  # noqa: E402
from core.enums import ElementType, RuleType  # noqa: E402
from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from services.course_service import CourseService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402
from services.policy_service import PolicyService, PolicyConflictError  # noqa: E402
from services.verification_service import VerificationService  # noqa: E402


class VerificationServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.source_owl = DEFAULT_ONTOLOGY_PATH
        self.test_owl = "test_verification.owl"
        shutil.copy(self.source_owl, self.test_owl)

        self.core = OntologyCore(self.test_owl)
        self.course_service = CourseService(self.core)
        self.policy_service = PolicyService(self.core)
        self.verification = VerificationService(self.core)

        elements = [
            CourseElement(element_id="mod_v1", name="Module V1", element_type=ElementType.MODULE, parent_id="course_v"),
            CourseElement(element_id="mod_v2", name="Module V2", element_type=ElementType.MODULE, parent_id="course_v"),
            CourseElement(element_id="lec_v1", name="Lec V1", element_type=ElementType.LECTURE, parent_id="mod_v1"),
            CourseElement(element_id="lec_v2", name="Lec V2", element_type=ElementType.LECTURE, parent_id="mod_v2"),
        ]
        self.course_service.sync_course_structure("course_v", CourseSyncPayload(course_name="Verification Course", elements=elements))

    def tearDown(self):
        if os.path.exists(self.test_owl):
            os.remove(self.test_owl)

    def test_happy_path_all_green(self):
        self.policy_service.create_policy(PolicyCreate(
            source_element_id="lec_v2",
            rule_type=RuleType.COMPLETION,
            target_element_id="lec_v1",
            author_id="methodologist_smirnov",
        ))

        report = self.verification.verify("course_v").to_dict()

        self.assertIn("properties", report)
        self.assertEqual(report["properties"]["consistency"]["status"], "passed")
        self.assertEqual(report["properties"]["acyclicity"]["status"], "passed")
        self.assertEqual(report["properties"]["reachability"]["status"], "passed")

    def test_cycle_detected_pre_create_rejects_policy(self):
        self.policy_service.create_policy(PolicyCreate(
            source_element_id="lec_v2",
            rule_type=RuleType.COMPLETION,
            target_element_id="lec_v1",
            author_id="methodologist_smirnov",
        ))
        with self.assertRaises(ValueError):
            self.policy_service.create_policy(PolicyCreate(
                source_element_id="lec_v1",
                rule_type=RuleType.COMPLETION,
                target_element_id="lec_v2",
                author_id="methodologist_smirnov",
            ))

    def test_full_verification_includes_subsumption_keys(self):
        self.policy_service.create_policy(PolicyCreate(
            source_element_id="lec_v2",
            rule_type=RuleType.GRADE,
            target_element_id="lec_v1",
            passing_threshold=80.0,
            author_id="methodologist_smirnov",
        ))
        self.policy_service.create_policy(PolicyCreate(
            source_element_id="lec_v2",
            rule_type=RuleType.GRADE,
            target_element_id="lec_v1",
            passing_threshold=60.0,
            author_id="methodologist_smirnov",
        ))

        report = self.verification.verify("course_v", include_subsumption=True).to_dict()
        self.assertIn("redundancy", report["properties"])
        self.assertIn("subsumption", report["properties"])
        self.assertEqual(report["properties"]["redundancy"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
