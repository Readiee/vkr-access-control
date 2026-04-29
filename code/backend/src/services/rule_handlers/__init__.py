"""Реестр хэндлеров типов правил доступа

REGISTRY[rule_type_str] → RuleHandler — единая точка диспетчеризации для
GraphValidator, VerificationService, policy_formatters и PolicyService.

Использование:
    from services.rule_handlers import REGISTRY

    handler = REGISTRY.get(rule_type)
    if handler:
        handler.add_dependency_edges(graph, onto, policy, source_id, recurse, depth)
"""
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

REGISTRY: Dict[str, RuleHandler] = {}


def _register(*handlers: RuleHandler) -> None:
    for h in handlers:
        REGISTRY[h.rule_type] = h


_register(
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

__all__ = ["REGISTRY", "RuleHandler"]
