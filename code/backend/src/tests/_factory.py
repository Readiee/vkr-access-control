"""Фабрика зависимостей для тестов: собирает весь граф сервисов вокруг одного World

Сервисы принимают явные зависимости (CacheManager, ReasoningOrchestrator,
соседние сервисы). Чтобы не повторять конструирование в каждом setUp, тесты
вызывают build_bundle(owl_path, world) и получают готовый набор
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Optional

from owlready2 import World

from core.config import DEFAULT_ONTOLOGY_PATH
from services.access import AccessService
from services.cache_manager import CacheManager
from services.integration_service import IntegrationService
from services.ontology_core import OntologyCore
from services.policy_service import PolicyService
from services.progress_service import ProgressService
from services.reasoning import ReasoningOrchestrator
from services.rollup_service import RollupService
from services.sandbox_service import SandboxService
from services.verification import VerificationService


def make_temp_onto_copy(prefix: str = "vkr_test_") -> str:
    """Копия базовой онтологии во временный каталог системы

    Путь возвращается вызывающему, чистка — на его tearDown. CWD не
    засоряется, крашнутый прогон оставит файл в %TMP%, а не в дереве репозитория
    """
    fd, path = tempfile.mkstemp(suffix=".owl", prefix=prefix)
    os.close(fd)
    shutil.copy(DEFAULT_ONTOLOGY_PATH, path)
    return path


@dataclass
class ServiceBundle:
    core: OntologyCore
    cache: CacheManager
    reasoner: ReasoningOrchestrator
    rollup: RollupService
    access: AccessService
    progress: ProgressService
    policy: PolicyService
    verification: VerificationService
    sandbox: SandboxService
    integration: IntegrationService


def build_bundle(owl_path: str, world: Optional[World] = None) -> ServiceBundle:
    """Собрать полный граф сервисов для тестового World; Redis=None"""
    core = OntologyCore(owl_path, world=world)
    cache = CacheManager(None, onto_path=owl_path)  # без Redis — CacheManager становится no-op
    reasoner = ReasoningOrchestrator(core.onto)
    rollup = RollupService(core)
    access = AccessService(core, cache=cache, reasoner=reasoner)
    progress = ProgressService(core, reasoner=reasoner, rollup=rollup, access=access)
    policy = PolicyService(core, reasoner=reasoner, cache=cache)
    verification = VerificationService(core, reasoner=reasoner, cache=cache)
    sandbox = SandboxService(core, reasoner=reasoner, access=access, progress=progress)
    integration = IntegrationService(core, verification=verification, cache=cache)
    return ServiceBundle(
        core=core,
        cache=cache,
        reasoner=reasoner,
        rollup=rollup,
        access=access,
        progress=progress,
        policy=policy,
        verification=verification,
        sandbox=sandbox,
        integration=integration,
    )
