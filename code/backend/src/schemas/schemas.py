"""Pydantic-модели запросов и ответов API."""
from pydantic import BaseModel, Field, model_validator, ConfigDict, AliasChoices
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

from core.enums import RuleType, ElementType, ProgressStatus, EventType


class Competency(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = Field(None, description="ID родительской компетенции")


class CourseElementMeta(BaseModel):
    id: str
    name: str
    type: ElementType
    is_mandatory: bool = True


class Group(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = Field(None, description="ID прямого родителя по is_subgroup_of")


class OntologyMeta(BaseModel):
    """Метаданные онтологии для фронтенда."""
    rule_types: List[RuleType]
    statuses: List[ProgressStatus]
    competencies: List[Competency]
    course_elements: List[CourseElementMeta]
    groups: List[Group] = Field(default_factory=list)


class AggregateFunction(str, Enum):
    AVG = "AVG"
    SUM = "SUM"
    COUNT = "COUNT"


class PolicyBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source_element_id: Optional[str] = Field(
        None,
        description=(
            "ID защищаемого элемента. Пусто — политика существует как подполитика "
            "композита и не привязана к элементу напрямую."
        ),
    )
    rule_type: RuleType
    target_element_id: Optional[str] = Field(None, description="ID целевого элемента (grade/completion/viewed)")
    target_competency_id: Optional[str] = Field(None, description="ID целевой компетенции (competency_required)")
    passing_threshold: Optional[float] = Field(None, description="Порог для grade_required/aggregate_required")
    valid_from: Optional[datetime] = Field(
        None,
        alias="available_from",
        validation_alias=AliasChoices("valid_from", "available_from"),
        serialization_alias="valid_from",
    )
    valid_until: Optional[datetime] = Field(
        None,
        alias="available_until",
        validation_alias=AliasChoices("valid_until", "available_until"),
        serialization_alias="valid_until",
    )
    restricted_to_group_id: Optional[str] = Field(None, description="ID группы для group_restricted")
    subpolicy_ids: Optional[List[str]] = Field(
        None,
        description=(
            "ID подполитик для and_combination/or_combination. "
            "and_combination: 2–3 (ограничение SWRL-шаблонов); or_combination: от 2 без верхней границы."
        ),
    )
    aggregate_function: Optional[AggregateFunction] = Field(None, description="AVG/SUM/COUNT")
    aggregate_element_ids: Optional[List[str]] = Field(None, description="ID элементов для агрегата")
    author_id: str = Field(..., description="ID методиста")


class PolicyCreate(PolicyBase):
    is_active: bool = True
    nested_subpolicies: Optional[List["PolicyCreate"]] = Field(
        None,
        description=(
            "Для and_combination: новые подполитики, создаваемые атомарно вместе с родителем. "
            "Альтернатива subpolicy_ids."
        ),
    )

    @model_validator(mode='after')
    def validate_by_rule_type(self) -> 'PolicyCreate':
        rt = self.rule_type if isinstance(self.rule_type, str) else self.rule_type.value

        if rt in {RuleType.COMPLETION.value, RuleType.VIEWED.value}:
            if not self.target_element_id:
                raise ValueError(f"Для {rt} обязателен target_element_id.")
        elif rt == RuleType.GRADE.value:
            if not self.target_element_id:
                raise ValueError("Для grade_required обязателен target_element_id.")
            if self.passing_threshold is None:
                raise ValueError("Для grade_required обязателен passing_threshold.")
        elif rt == RuleType.COMPETENCY.value:
            if not self.target_competency_id:
                raise ValueError("Для competency_required обязателен target_competency_id.")
        elif rt == RuleType.DATE.value:
            if self.valid_from is None or self.valid_until is None:
                raise ValueError("Для date_restricted обязательны valid_from и valid_until.")
            if self.valid_from > self.valid_until:
                raise ValueError("valid_from должно быть раньше valid_until.")
            for field_name, ts in (("valid_from", self.valid_from), ("valid_until", self.valid_until)):
                if ts.minute != 0 or ts.second != 0 or ts.microsecond != 0:
                    raise ValueError(
                        f"{field_name} должен быть выставлен на целый час "
                        f"(минуты/секунды = 0), получено {ts.isoformat()}."
                    )
        elif rt in {RuleType.AND.value, RuleType.OR.value}:
            nested = self.nested_subpolicies or []
            ids = self.subpolicy_ids or []
            total = len(nested) + len(ids)
            if total < 2:
                raise ValueError(f"Для {rt} нужно минимум 2 подполитики (через nested или subpolicy_ids).")
            if rt == RuleType.AND.value and total > 3:
                raise ValueError(
                    "and_combination поддерживает максимум 3 подполитики. "
                    "Для более широких условий — соберите их в отдельные правила "
                    "и свяжите AND-правилом верхнего уровня."
                )
            if ids and len(set(ids)) != len(ids):
                raise ValueError("subpolicy_ids должны быть уникальны.")
            for child in nested:
                child_rt = child.rule_type if isinstance(child.rule_type, str) else child.rule_type.value
                if child_rt in {RuleType.AND.value, RuleType.OR.value}:
                    raise ValueError("Вложенные композиты сейчас не поддержаны; используйте плоский список условий.")
        elif rt == RuleType.GROUP.value:
            if not self.restricted_to_group_id:
                raise ValueError("Для group_restricted обязателен restricted_to_group_id.")
        elif rt == RuleType.AGGREGATE.value:
            if self.aggregate_function is None:
                raise ValueError("Для aggregate_required обязателен aggregate_function.")
            if not self.aggregate_element_ids:
                raise ValueError("Для aggregate_required обязателен aggregate_element_ids.")
            if self.passing_threshold is None:
                raise ValueError("Для aggregate_required обязателен passing_threshold.")
        return self


PolicyCreate.model_rebuild()


class Policy(PolicyBase):
    id: str
    is_active: bool
    name: Optional[str] = None
    target_element_name: Optional[str] = None
    target_competency_name: Optional[str] = None
    restricted_to_group_name: Optional[str] = None
    aggregate_element_names: Optional[List[str]] = None
    subpolicies_detail: Optional[List["Policy"]] = Field(
        None, description="Развёрнутые подусловия композита (только верхний уровень)"
    )


Policy.model_rebuild()


class TogglePolicy(BaseModel):
    is_active: bool


class CourseElement(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    element_id: str
    name: str
    element_type: ElementType
    parent_id: Optional[str] = None
    is_mandatory: Optional[bool] = True
    order_index: Optional[int] = Field(default=None, description="Порядковый номер; None — берётся позиция в массиве")


class CourseSyncPayload(BaseModel):
    course_name: str
    elements: List[CourseElement]


class ProgressEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    student_id: str
    element_id: str
    event_type: EventType
    grade: Optional[float] = None
    timestamp: Optional[datetime] = None


class AvailableElements(BaseModel):
    available_elements: List[str]


class SandboxProgressPayload(BaseModel):
    element_id: str
    status: ProgressStatus
    grade: Optional[float] = None


class SandboxCompetencyPayload(BaseModel):
    competency_id: str
    has_competency: bool


class CourseTreeNode(BaseModel):
    key: str
    data: Dict[str, Any]
    children: Optional[List['CourseTreeNode']] = []


if hasattr(CourseTreeNode, 'model_rebuild'):
    CourseTreeNode.model_rebuild()
else:
    CourseTreeNode.update_forward_refs()


class PropertyReportResponse(BaseModel):
    """Отчёт по одному верифицируемому свойству."""
    status: str = Field(..., description='"passed" | "failed" | "unknown"')
    violations: List[Dict[str, Any]] = Field(default_factory=list)


class VerificationReportResponse(BaseModel):
    course_id: str
    run_id: str
    timestamp: str
    duration_ms: int
    partial: bool = Field(
        ...,
        description="True, если reasoning не завершился штатно (timeout/error) и часть свойств — unknown",
    )
    properties: Dict[str, PropertyReportResponse] = Field(
        ..., description="consistency, acyclicity, reachability, redundancy, subsumption"
    )
    summary: str
    ontology_version: Optional[str] = Field(None, description="sha256 онтологии на момент расчёта")


class JustificationNodeResponse(BaseModel):
    """Узел дерева обоснования доступа или блокировки."""
    status: str = Field(..., description='"satisfied" | "unsatisfied" | "available" | "unavailable"')
    rule_template: str = Field(..., description="completion_required, meta:is_available_for, …")
    policy_id: Optional[str] = None
    variable_bindings: Dict[str, Any] = Field(default_factory=dict)
    body_facts: List[Dict[str, Any]] = Field(default_factory=list)
    children: List["JustificationNodeResponse"] = Field(default_factory=list)
    note: Optional[str] = None


JustificationNodeResponse.model_rebuild()


class BlockedPolicyResponse(BaseModel):
    policy_id: str
    policy_name: str
    rule_type: str
    satisfied: bool
    failure_reason: Optional[str] = None
    witness: Dict[str, Any] = Field(default_factory=dict)


class BlockingExplanationResponse(BaseModel):
    """Ответ на запрос «почему элемент (не)доступен студенту»."""
    element_id: str
    element_name: str
    student_id: str
    student_name: str
    is_available: bool
    cascade_blocker: Optional[str] = Field(
        None, description="ID ближайшего родителя, заблокировавшего доступ каскадно"
    )
    cascade_blocker_name: Optional[str] = None
    cascade_reason: Optional[str] = None
    applicable_policies: List[BlockedPolicyResponse] = Field(default_factory=list)
    justification: JustificationNodeResponse
