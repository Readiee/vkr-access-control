"""Реестр хэндлеров типов правил."""
from __future__ import annotations

from typing import Dict

from services.rule_handlers._base import RuleHandler
from services.rule_handlers._atomic import (
    AggregateHandler,
    CompetencyHandler,
    CompletionHandler,
    DateHandler,
    GradeHandler,
    GroupHandler,
    ViewedHandler,
)
from services.rule_handlers._composite import AndHandler, OrHandler


REGISTRY: Dict[str, RuleHandler] = {
    h.rule_type: h
    for h in (
        CompletionHandler(),
        ViewedHandler(),
        GradeHandler(),
        CompetencyHandler(),
        DateHandler(),
        GroupHandler(),
        AggregateHandler(),
        AndHandler(),
        OrHandler(),
    )
}


__all__ = ["REGISTRY", "RuleHandler"]
