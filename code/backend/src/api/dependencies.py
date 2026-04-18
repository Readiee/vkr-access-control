from functools import lru_cache
from fastapi import Depends
from core.config import settings
from services.ontology_core import OntologyCore
from services.policy_service import PolicyService
from services.course_service import CourseService
from services.progress_service import ProgressService
from services.sandbox_service import SandboxService


@lru_cache()
def get_ontology_core() -> OntologyCore:
    """Обеспечивает DI для OntologyCore (Singleton)."""
    return OntologyCore(onto_path=settings.ONTOLOGY_FILE_PATH)

def get_policy_service(core: OntologyCore = Depends(get_ontology_core)) -> PolicyService:
    """Обеспечивает DI для PolicyService."""
    return PolicyService(core)

def get_course_service(core: OntologyCore = Depends(get_ontology_core)) -> CourseService:
    """Обеспечивает DI для CourseService."""
    return CourseService(core)

def get_progress_service(core: OntologyCore = Depends(get_ontology_core)) -> ProgressService:
    """Обеспечивает DI для ProgressService."""
    return ProgressService(core)


def get_sandbox_service(
    core: OntologyCore = Depends(get_ontology_core), 
    progress_service: ProgressService = Depends(get_progress_service)
) -> SandboxService:
    """Обеспечивает DI для SandboxService."""
    return SandboxService(core, progress_service)
