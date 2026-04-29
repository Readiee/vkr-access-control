"""Pydantic-модели интеграционного слоя: синхронизация курса, прогресс, дерево."""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.enums import ElementType, EventType


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


class ElementCompetenciesPayload(BaseModel):
    competency_ids: List[str] = Field(default_factory=list)


class ElementMandatoryPayload(BaseModel):
    is_mandatory: bool


class CourseTreeNode(BaseModel):
    key: str
    data: Dict[str, Any]
    children: Optional[List['CourseTreeNode']] = []


CourseTreeNode.model_rebuild()
