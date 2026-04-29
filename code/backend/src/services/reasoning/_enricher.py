"""Подготовка ABox перед запуском резонера.

SWRL не умеет брать текущее время и считать агрегаты, поэтому реифицируем
эти значения в индивиды. OWL монотонен и не делает truth maintenance —
старые выводы (satisfies, is_available_for) чистим целиком перед каждым
прогоном, не точечно.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List

from owlready2 import destroy_entity

from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)

CURRENT_TIME_INDIVIDUAL = "current_time_ind"


def clear_inferred_triples(onto: Any) -> None:
    for student in onto.Student.instances():
        if hasattr(student, "satisfies"):
            student.satisfies = []
    for element in onto.CourseStructure.instances():
        if hasattr(element, "is_available_for"):
            element.is_available_for = []


def enrich_current_time(onto: Any, now: datetime | None = None) -> Any:
    """Положить в ABox единственный индивид CurrentTime."""
    for ind in list(onto.CurrentTime.instances()):
        destroy_entity(ind)
    now = now or datetime.utcnow()
    ct = onto.CurrentTime(CURRENT_TIME_INDIVIDUAL)
    ct.has_value = now  # functional, скаляр
    return ct


def enrich_aggregates(onto: Any) -> int:
    """Пересчитать AggregateFact для всех активных aggregate_required-политик.

    Один факт на пару (студент, политика) с computed_value = AVG/SUM/COUNT
    по оценкам за aggregate_elements. Возвращает число созданных фактов.
    """
    for fact in list(onto.AggregateFact.instances()):
        destroy_entity(fact)

    aggregate_policies = [
        p for p in onto.AccessPolicy.instances()
        if get_owl_prop(p, "rule_type") == "aggregate_required"
        and get_owl_prop(p, "is_active", True) is True
    ]
    if not aggregate_policies:
        return 0

    students = list(onto.Student.instances())
    created = 0

    for policy in aggregate_policies:
        fn = get_owl_prop(policy, "aggregate_function") or "AVG"
        elements = list(getattr(policy, "aggregate_elements", []) or [])
        if not elements:
            logger.warning(
                "aggregate_required policy %s пропущена: aggregate_elements пуст",
                policy.name,
            )
            continue

        element_names = {e.name for e in elements}

        for student in students:
            grades: List[float] = []
            for pr in getattr(student, "has_progress_record", []) or []:
                target = get_owl_prop(pr, "refers_to_element")
                grade = get_owl_prop(pr, "has_grade")
                if target is not None and target.name in element_names and grade is not None:
                    grades.append(grade)

            if not grades and fn != "COUNT":
                continue

            value = _apply_aggregate(fn, grades)
            fact = onto.AggregateFact(f"agg_{student.name}_{policy.name}")
            fact.for_student = student
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
