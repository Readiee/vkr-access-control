"""Pydantic-модели запросов и ответов Semantic Rules API."""
from pydantic import BaseModel, Field, model_validator, ConfigDict, AliasChoices
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

from core.enums import RuleType, ElementType, ProgressStatus, EventType


class Competency(BaseModel):
    """Компетенция из онтологии."""
    id: str = Field(..., description="ID компетенции (напр. 'comp_python')")
    name: str = Field(..., description="Название (напр. 'Язык Python')")
    parent_id: Optional[str] = Field(None, description="ID родительской компетенции для иерархии")


class CourseElementMeta(BaseModel):
    """Краткое представление элемента курса для UI."""
    id: str = Field(..., description="Локальный ID элемента")
    name: str = Field(..., description="Название элемента")
    type: ElementType = Field(..., description="Тип элемента (course, module, lecture, test)")
    is_mandatory: bool = Field(default=True, description="Является ли элемент обязательным")


class Group(BaseModel):
    """Студенческая группа для group_restricted."""
    id: str = Field(..., description="ID группы (напр. 'grp_advanced')")
    name: str = Field(..., description="Название группы")


class OntologyMeta(BaseModel):
    """Метаданные онтологии для фронтенда."""
    rule_types: List[RuleType] = Field(..., description="Список поддерживаемых типов правил")
    statuses: List[ProgressStatus] = Field(..., description="Список статусов отслеживания")
    competencies: List[Competency] = Field(..., description="Список доступных компетенций")
    course_elements: List[CourseElementMeta] = Field(..., description="Список элементов структуры курса")
    groups: List[Group] = Field(default_factory=list, description="Список доступных групп студентов")


class AggregateFunction(str, Enum):
    """Допустимые функции агрегата для aggregate_required."""
    AVG = "AVG"
    SUM = "SUM"
    COUNT = "COUNT"


class PolicyBase(BaseModel):
    """Базовые поля политики доступа."""
    model_config = ConfigDict(use_enum_values=True)

    source_element_id: Optional[str] = Field(
        None,
        description=(
            "ID защищаемого элемента. Пусто → политика существует как "
            "подполитика композита и не привязана к элементу напрямую."
        ),
    )
    rule_type: RuleType = Field(..., description="Тип применяемого правила")
    target_element_id: Optional[str] = Field(None, description="ID целевого элемента (для grade/completion/viewed)")
    target_competency_id: Optional[str] = Field(None, description="ID целевой компетенции (для competency_required)")
    passing_threshold: Optional[float] = Field(None, description="Пороговая оценка для grade_required/aggregate_required")
    valid_from: Optional[datetime] = Field(
        None,
        description="Дата открытия доступа (date_restricted)",
        alias="available_from",
        validation_alias=AliasChoices("valid_from", "available_from"),
        serialization_alias="valid_from",
    )
    valid_until: Optional[datetime] = Field(
        None,
        description="Дата закрытия доступа (date_restricted)",
        alias="available_until",
        validation_alias=AliasChoices("valid_until", "available_until"),
        serialization_alias="valid_until",
    )
    restricted_to_group_id: Optional[str] = Field(None, description="ID группы студентов для group_restricted")
    subpolicy_ids: Optional[List[str]] = Field(
        None,
        description=(
            "ID подполитик для and_combination/or_combination. "
            "Для and_combination — от 2 до 3 (ограничение SWRL-шаблонов, см. PROJECT_BIBLE §7 24.04). "
            "Для or_combination — от 2 без верхней границы."
        ),
    )
    aggregate_function: Optional[AggregateFunction] = Field(
        None, description="AVG/SUM/COUNT для aggregate_required"
    )
    aggregate_element_ids: Optional[List[str]] = Field(
        None, description="ID элементов, по которым считается агрегат"
    )
    author_id: str = Field(..., description="ID методиста, создавшего правило")


class PolicyCreate(PolicyBase):
    """Payload для создания новой политики."""
    is_active: bool = Field(True, description="Флаг активности (по умолчанию: True)")
    nested_subpolicies: Optional[List["PolicyCreate"]] = Field(
        None,
        description=(
            "Для and_combination — новые подполитики, создаваемые атомарно вместе "
            "с родителем. Альтернатива subpolicy_ids (привязка к уже существующим)."
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
            # Шаг границ — ровно 1 час. Позволяет держать фиксированный TTL=3600
            # кэша доступа без отдельного cron-воркера: к моменту истечения TTL
            # все датные границы уже пересечены.
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
    """Политика доступа с идентификатором, статусом активности и UI-extras."""
    id: str = Field(..., description="Сгенерированный ID политики")
    is_active: bool = Field(..., description="Флаг активности правила")
    name: Optional[str] = Field(None, description="Человеческое название (label или auto-описание)")
    target_element_name: Optional[str] = Field(None, description="Название целевого элемента")
    target_competency_name: Optional[str] = Field(None, description="Название целевой компетенции")
    restricted_to_group_name: Optional[str] = Field(None, description="Название группы")
    aggregate_element_names: Optional[List[str]] = Field(None, description="Названия элементов агрегата")
    subpolicies_detail: Optional[List["Policy"]] = Field(
        None, description="Развёрнутые подусловия композита (только верхний уровень)"
    )


Policy.model_rebuild()


class TogglePolicy(BaseModel):
    """Payload для переключения активности политики."""
    is_active: bool = Field(..., description="Новое состояние активности")


class CourseElement(BaseModel):
    """Элемент структуры курса."""
    model_config = ConfigDict(use_enum_values=True)

    element_id: str = Field(..., description="ID элемента")
    name: str = Field(..., description="Человекочитаемое название")
    element_type: ElementType = Field(..., description="Тип элемента")
    parent_id: Optional[str] = Field(None, description="ID родительского контейнера или курса")
    is_mandatory: Optional[bool] = Field(default=True, description="Является ли элемент обязательным для прохождения")
    order_index: Optional[int] = Field(default=None, description="Порядковый номер элемента. Если не передан, вычисляется из позиции в массиве.")


class CourseSyncPayload(BaseModel):
    """Payload синхронизации структуры курса."""
    course_name: str = Field(..., description="Название курса")
    elements: List[CourseElement] = Field(..., description="Плоский список всех элементов иерархии")


class ProgressEvent(BaseModel):
    """Событие успеваемости студента из СДО."""
    model_config = ConfigDict(use_enum_values=True)

    student_id: str = Field(..., description="ID студента")
    element_id: str = Field(..., description="ID элемента, с которым взаимодействовал студент")
    event_type: EventType = Field(..., description="Тип произведённого действия")
    grade: Optional[float] = Field(None, description="Полученная оценка (если есть)")
    timestamp: Optional[datetime] = Field(None, description="Время события")


class AvailableElements(BaseModel):
    """Ответ с логически выведенными доступными элементами."""
    available_elements: List[str] = Field(..., description="ID элементов, доступных студенту")


class SandboxProgressPayload(BaseModel):
    """Payload для симуляции прогресса в Песочнице (для тестового студента)."""
    element_id: str
    status: ProgressStatus
    grade: Optional[float] = None


class SandboxCompetencyPayload(BaseModel):
    """Payload для выдачи/отзыва компетенций в Песочнице (для тестового студента)."""
    competency_id: str
    has_competency: bool


class CourseTreeNode(BaseModel):
    """Узел дерева курса для UI."""
    key: str
    data: Dict[str, Any]
    children: Optional[List['CourseTreeNode']] = []

if hasattr(CourseTreeNode, 'model_rebuild'):
    CourseTreeNode.model_rebuild()
else:
    CourseTreeNode.update_forward_refs()
