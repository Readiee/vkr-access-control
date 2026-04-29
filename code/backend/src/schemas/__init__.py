"""Pydantic-модели запросов и ответов API.

Раскладка по доменам:
    ontology      — справочные метаданные (TBox-проекция для фронта)
    policy        — политики доступа и их CRUD-обёртки
    integration   — приём данных СДО (sync курса, события прогресса)
    sandbox       — ручные подмены ABox в режиме песочницы
    access        — проверка доступности и обоснование блокировок
    verification  — отчёты статической верификации онтологии
"""
from schemas.ontology import (
    Competency,
    CourseElementMeta,
    Group,
    OntologyMeta,
)
from schemas.policy import (
    AggregateFunction,
    PolicyBase,
    PolicyCreate,
    Policy,
    TogglePolicy,
)
from schemas.integration import (
    CourseElement,
    CourseSyncPayload,
    ProgressEvent,
    ElementCompetenciesPayload,
    ElementMandatoryPayload,
    CourseTreeNode,
)
from schemas.sandbox import (
    SandboxProgressPayload,
    SandboxCompetencyPayload,
    SandboxGroupsPayload,
)
from schemas.access import (
    AvailableElements,
    JustificationNodeResponse,
    BlockedPolicyResponse,
    BlockingExplanationResponse,
)
from schemas.verification import (
    PropertyReportResponse,
    VerificationReportResponse,
)

__all__ = [
    "Competency",
    "CourseElementMeta",
    "Group",
    "OntologyMeta",
    "AggregateFunction",
    "PolicyBase",
    "PolicyCreate",
    "Policy",
    "TogglePolicy",
    "CourseElement",
    "CourseSyncPayload",
    "ProgressEvent",
    "ElementCompetenciesPayload",
    "ElementMandatoryPayload",
    "CourseTreeNode",
    "SandboxProgressPayload",
    "SandboxCompetencyPayload",
    "SandboxGroupsPayload",
    "AvailableElements",
    "JustificationNodeResponse",
    "BlockedPolicyResponse",
    "BlockingExplanationResponse",
    "PropertyReportResponse",
    "VerificationReportResponse",
]
