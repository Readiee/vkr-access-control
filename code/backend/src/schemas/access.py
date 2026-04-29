"""Pydantic-модели проверки доступа и обоснования блокировок."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class AvailableElements(BaseModel):
    available_elements: List[str]


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
