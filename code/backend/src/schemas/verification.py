"""Pydantic-модели отчёта о верификации онтологии."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


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
