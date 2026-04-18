from enum import Enum


class RuleType(str, Enum):
    """Типы правил доступа."""
    VIEWED = "viewed_required"
    COMPLETION = "completion_required"
    GRADE = "grade_required"
    COMPETENCY = "competency_required"
    DATE = "date_restricted"


# Набор правил, которые вычисляются на уровне OWL-ризонера (SWRL)
SWRL_RULE_TYPES = {
    RuleType.VIEWED.value,
    RuleType.COMPLETION.value,
    RuleType.GRADE.value,
    RuleType.COMPETENCY.value
}


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
