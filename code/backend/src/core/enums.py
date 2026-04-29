"""Перечисления и OWL-константы, общие для API-схем и сервисов."""
from __future__ import annotations

from enum import Enum


class RuleType(str, Enum):
    """Типы правил доступа. Значение совпадает с rule_type в OWL ABox."""
    VIEWED = "viewed_required"
    COMPLETION = "completion_required"
    GRADE = "grade_required"
    COMPETENCY = "competency_required"
    DATE = "date_restricted"
    AND = "and_combination"
    OR = "or_combination"
    GROUP = "group_restricted"
    AGGREGATE = "aggregate_required"


COMPOSITE_RULE_TYPES: frozenset[str] = frozenset({RuleType.AND.value, RuleType.OR.value})


class ElementType(str, Enum):
    """Типы структурных элементов курса."""
    COURSE = "course"
    MODULE = "module"
    LECTURE = "lecture"
    TEST = "test"
    PRACTICE = "practice"
    ASSIGNMENT = "assignment"


class ProgressStatus(str, Enum):
    """Статусы прохождения элементов."""
    VIEWED = "viewed"
    COMPLETED = "completed"
    PASSED = "passed"
    FAILED = "failed"


class EventType(str, Enum):
    """Типы событий успеваемости из СДО."""
    VIEWED = "viewed"
    COMPLETED = "completed"
    GRADED = "graded"
    FAILED = "failed"


class ReasoningStatus(str, Enum):
    """Итог одного прогона DL-резонера."""
    OK = "ok"
    TIMEOUT = "timeout"
    INCONSISTENT = "inconsistent"
    ERROR = "error"


class VerificationStatus(str, Enum):
    """Итог проверки одного формального свойства курса."""
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class JustificationStatus(str, Enum):
    """Статус узла дерева обоснования (SLD-trace тела SWRL)."""
    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


# Префикс OWL-индивидов прогресса: status_completed, status_viewed, status_failed
OWL_STATUS_PREFIX = "status_"

# Родовой fallback-класс для элементов курса с неизвестным конкретным типом
COURSE_STRUCTURE_OWL_CLASS = "CourseStructure"

ELEMENT_TYPE_TO_OWL_CLASS: dict[str, str] = {
    ElementType.COURSE.value: "Course",
    ElementType.MODULE.value: "Module",
    ElementType.LECTURE.value: "Lecture",
    ElementType.TEST.value: "Test",
    ElementType.PRACTICE.value: "Practice",
    ElementType.ASSIGNMENT.value: "Assignment",
}
