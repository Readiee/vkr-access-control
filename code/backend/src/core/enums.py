from enum import Enum


class RuleType(str, Enum):
    """Типы правил доступа."""
    VIEWED = "viewed_required"
    COMPLETION = "completion_required"
    GRADE = "grade_required"
    COMPETENCY = "competency_required"
    DATE = "date_restricted"
    AND = "and_combination"
    OR = "or_combination"
    GROUP = "group_restricted"
    AGGREGATE = "aggregate_required"


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
