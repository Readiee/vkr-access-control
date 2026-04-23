"""DI-граф сервисов (FastAPI Depends).

По DSL §44–§123: OntologyCore — тонкий, CacheManager/ReasoningOrchestrator —
отдельные Core-компоненты. Сервисы Service Layer получают явные зависимости
через Depends (не лезут в core.*). Это убирает service-locator antipattern,
делает зависимости видимыми в сигнатурах конструкторов и упрощает мокирование.
"""
from functools import lru_cache
from typing import Optional

import redis
from fastapi import Depends

from core.config import settings
from services.access import AccessService
from services.cache_manager import CacheManager
from services.integration_service import IntegrationService
from services.ontology_core import OntologyCore, connect_redis
from services.policy_service import PolicyService
from services.progress_service import ProgressService
from services.reasoning import ReasoningOrchestrator
from services.rollup_service import RollupService
from services.sandbox_service import SandboxService
from services.verification import VerificationService


@lru_cache()
def get_ontology_core() -> OntologyCore:
    return OntologyCore(onto_path=settings.ONTOLOGY_FILE_PATH)


@lru_cache()
def get_redis_client() -> Optional[redis.Redis]:
    return connect_redis(settings.REDIS_URL)


def get_cache_manager(
    redis_client: Optional[redis.Redis] = Depends(get_redis_client),
) -> CacheManager:
    return CacheManager(redis_client)


def get_reasoning_orchestrator(
    core: OntologyCore = Depends(get_ontology_core),
) -> ReasoningOrchestrator:
    return ReasoningOrchestrator(core.onto)


def get_access_service(
    core: OntologyCore = Depends(get_ontology_core),
    cache: CacheManager = Depends(get_cache_manager),
    reasoner: ReasoningOrchestrator = Depends(get_reasoning_orchestrator),
) -> AccessService:
    return AccessService(core, cache=cache, reasoner=reasoner)


def get_rollup_service(
    core: OntologyCore = Depends(get_ontology_core),
) -> RollupService:
    return RollupService(core)


def get_progress_service(
    core: OntologyCore = Depends(get_ontology_core),
    reasoner: ReasoningOrchestrator = Depends(get_reasoning_orchestrator),
    rollup: RollupService = Depends(get_rollup_service),
    access: AccessService = Depends(get_access_service),
) -> ProgressService:
    return ProgressService(core, reasoner=reasoner, rollup=rollup, access=access)


def get_policy_service(
    core: OntologyCore = Depends(get_ontology_core),
    reasoner: ReasoningOrchestrator = Depends(get_reasoning_orchestrator),
    cache: CacheManager = Depends(get_cache_manager),
) -> PolicyService:
    return PolicyService(core, reasoner=reasoner, cache=cache)


def get_verification_service(
    core: OntologyCore = Depends(get_ontology_core),
    reasoner: ReasoningOrchestrator = Depends(get_reasoning_orchestrator),
    cache: CacheManager = Depends(get_cache_manager),
) -> VerificationService:
    return VerificationService(core, reasoner=reasoner, cache=cache)


def get_sandbox_service(
    core: OntologyCore = Depends(get_ontology_core),
    reasoner: ReasoningOrchestrator = Depends(get_reasoning_orchestrator),
    access: AccessService = Depends(get_access_service),
    progress: ProgressService = Depends(get_progress_service),
) -> SandboxService:
    return SandboxService(core, reasoner=reasoner, access=access, progress=progress)


def get_integration_service(
    core: OntologyCore = Depends(get_ontology_core),
    verification: VerificationService = Depends(get_verification_service),
    cache: CacheManager = Depends(get_cache_manager),
) -> IntegrationService:
    return IntegrationService(core, verification=verification, cache=cache)
