"""Pydantic-модели метаданных онтологии для фронтенда."""
from pydantic import BaseModel, Field
from typing import List, Optional

from core.enums import RuleType, ElementType, ProgressStatus


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
