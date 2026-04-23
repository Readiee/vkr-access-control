"""Подготовка ABox перед запуском резонера — приватный модуль ReasoningOrchestrator.

SWRL не умеет брать текущее время и считать агрегаты — это делаем здесь, реифицируя
значения в индивидов, на которые правила могут ссылаться. OWL монотонен и не поддерживает
truth maintenance, поэтому старые выводы (satisfies, is_available_for) чистим целиком
перед каждым прогоном, а не пытаемся обновить точечно.

В DSL этот модуль не выделен как отдельный компонент — это деталь pipeline A2
внутри ReasoningOrchestrator. Импортируется только из reasoning_orchestrator.py.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List

from owlready2 import destroy_entity

logger = logging.getLogger(__name__)

CURRENT_TIME_INDIVIDUAL = "current_time_ind"


def clear_inferred_triples(onto: Any) -> None:
    """Удалить ранее выведенные satisfies и is_available_for со всех индивидов."""
    for student in onto.Student.instances():
        if hasattr(student, "satisfies"):
            student.satisfies = []
    for element in onto.CourseStructure.instances():
        if hasattr(element, "is_available_for"):
            element.is_available_for = []


def enrich_current_time(onto: Any, now: datetime | None = None) -> Any:
    """Положить в ABox одиночный индивид CurrentTime с текущим временем.

    Старые экземпляры уничтожаются — класс должен содержать ровно один индивид.
    """
    for ind in list(onto.CurrentTime.instances()):
        destroy_entity(ind)
    now = now or datetime.utcnow()
    ct = onto.CurrentTime(CURRENT_TIME_INDIVIDUAL)
    ct.has_value = now  # functional property, scalar API
    return ct


def enrich_aggregates(onto: Any) -> int:
    """Пересчитать AggregateFact для всех активных aggregate_required-политик.

    Удаляет все старые факты и создаёт новые — по одному на пару (студент, политика)
    — где значение = AVG/SUM/COUNT по оценкам за aggregate_elements. Возвращает число
    созданных фактов.
    """
    for fact in list(onto.AggregateFact.instances()):
        destroy_entity(fact)

    created = 0
    aggregate_policies = [
        p for p in onto.AccessPolicy.instances()
        if _one(p.rule_type) == "aggregate_required" and _one(p.is_active)
    ]
    if not aggregate_policies:
        return 0

    students = list(onto.Student.instances())

    for policy in aggregate_policies:
        fn = _one(policy.aggregate_function) or "AVG"
        elements = list(getattr(policy, "aggregate_elements", []) or [])
        if not elements:
            logger.warning(
                "aggregate_required policy %s пропущена: aggregate_elements пуст",
                policy.name,
            )
            continue

        element_set = {e.name for e in elements}

        for student in students:
            grades: List[float] = [
                _one(pr.has_grade)
                for pr in getattr(student, "has_progress_record", [])
                if _one(pr.refers_to_element) is not None
                and _one(pr.refers_to_element).name in element_set
                and _one(pr.has_grade) is not None
            ]
            if not grades and fn != "COUNT":
                continue

            value = _apply_aggregate(fn, grades)
            fact = onto.AggregateFact(f"agg_{student.name}_{policy.name}")
            fact.for_student = student        # functional, scalar
            fact.for_policy = policy
            fact.computed_value = value
            created += 1

    return created


def _apply_aggregate(fn: str, grades: List[float]) -> float:
    fn = fn.upper()
    if fn == "AVG":
        return sum(grades) / len(grades)
    if fn == "SUM":
        return sum(grades)
    if fn == "COUNT":
        return float(len(grades))
    raise ValueError(f"Неизвестная aggregate_function: {fn}")


def _one(value: Any) -> Any:
    """Развернуть значение owlready-свойства в скаляр — берём первое из списка."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value
