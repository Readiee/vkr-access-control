"""Integration: VerificationService с реальным Pellet на временной онтологии."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from schemas.schemas import CourseElement, CourseSyncPayload, PolicyCreate  # noqa: E402
from core.enums import ElementType, RuleType  # noqa: E402
from core.config import DEFAULT_ONTOLOGY_PATH  # noqa: E402
from services.integration_service import IntegrationService  # noqa: E402
from services.ontology_core import OntologyCore  # noqa: E402
from services.policy_service import PolicyService  # noqa: E402
from services.verification import VerificationService  # noqa: E402


class VerificationServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        from tests._factory import make_temp_onto_copy
        self.source_owl = DEFAULT_ONTOLOGY_PATH
        self.test_owl = make_temp_onto_copy(prefix="vkr_verification_")

        self.core = OntologyCore(self.test_owl)
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
        self.verification = VerificationService(self.core, reasoner=self.reasoner, cache=self.cache)

        elements = [
            CourseElement(element_id="mod_v1", name="Module V1", element_type=ElementType.MODULE, parent_id="course_v"),
            CourseElement(element_id="mod_v2", name="Module V2", element_type=ElementType.MODULE, parent_id="course_v"),
            CourseElement(element_id="lec_v1", name="Lec V1", element_type=ElementType.LECTURE, parent_id="mod_v1"),
            CourseElement(element_id="lec_v2", name="Lec V2", element_type=ElementType.LECTURE, parent_id="mod_v2"),
        ]
        self.integration_service.sync_course_structure("course_v", CourseSyncPayload(course_name="Verification Course", elements=elements))

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

    def test_report_validates_against_pydantic_response_schema(self):
        from schemas.schemas import VerificationReportResponse

        self.policy_service.create_policy(PolicyCreate(
            source_element_id="lec_v2",
            rule_type=RuleType.COMPLETION,
            target_element_id="lec_v1",
            author_id="methodologist_smirnov",
        ))

        raw = self.verification.verify("course_v", include_subsumption=True).to_dict()
        validated = VerificationReportResponse.model_validate(raw)

        self.assertEqual(validated.course_id, "course_v")
        self.assertIn("consistency", validated.properties)
        self.assertIn("acyclicity", validated.properties)
        self.assertIn("reachability", validated.properties)
        self.assertIn("redundancy", validated.properties)
        self.assertIn("subsumption", validated.properties)
        # ontology_version проставляется даже без Redis: current_ontology_version()
        # читает файл напрямую по onto_path. CacheManager(None) с onto_path=None не
        # знает пути, поэтому здесь ожидаем None — но схема обязана принимать оба варианта.
        self.assertTrue(validated.ontology_version is None or isinstance(validated.ontology_version, str))


if __name__ == "__main__":
    unittest.main()
