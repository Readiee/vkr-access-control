"""Pydantic-модели песочницы: ручные подмены прогресса/компетенций/групп."""
from pydantic import BaseModel, Field
from typing import List, Optional

from core.enums import ProgressStatus


class SandboxProgressPayload(BaseModel):
    element_id: str
    status: ProgressStatus
    grade: Optional[float] = None


class SandboxCompetencyPayload(BaseModel):
    competency_id: str
    has_competency: bool


class SandboxGroupsPayload(BaseModel):
    group_ids: List[str] = Field(default_factory=list)
