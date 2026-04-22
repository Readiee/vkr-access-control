from functools import lru_cache

from fastapi import Depends

from core.config import settings
from services.access_service import AccessService
from services.course_service import CourseService
from services.ontology_core import OntologyCore
from services.policy_service import PolicyService
from services.progress_service import ProgressService
from services.sandbox_service import SandboxService
from services.verification_service import VerificationService


@lru_cache()
def get_ontology_core() -> OntologyCore:
    """DI для OntologyCore (singleton)."""
    return OntologyCore(onto_path=settings.ONTOLOGY_FILE_PATH)


def get_policy_service(core: OntologyCore = Depends(get_ontology_core)) -> PolicyService:
    return PolicyService(core)


def get_course_service(core: OntologyCore = Depends(get_ontology_core)) -> CourseService:
    return CourseService(core)


def get_access_service(core: OntologyCore = Depends(get_ontology_core)) -> AccessService:
    return AccessService(core)


def get_progress_service(core: OntologyCore = Depends(get_ontology_core)) -> ProgressService:
    return ProgressService(core)


def get_verification_service(core: OntologyCore = Depends(get_ontology_core)) -> VerificationService:
    return VerificationService(core)


def get_sandbox_service(
    core: OntologyCore = Depends(get_ontology_core),
    progress_service: ProgressService = Depends(get_progress_service),
) -> SandboxService:
    return SandboxService(core, progress_service)
