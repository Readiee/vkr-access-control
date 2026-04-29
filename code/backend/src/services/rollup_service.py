import logging
from typing import Callable

from core.enums import ProgressStatus
from utils.owl_utils import get_owl_prop, status_value_from_individual

logger = logging.getLogger(__name__)


class RollupService:
    """Восходящая агрегация: контейнер закрывается, когда все обязательные потомки закрыты."""

    def __init__(self, core):
        self.core = core

    def execute(self, student, child_element, update_callback: Callable[[str, str, ProgressStatus], None]) -> None:
        parent = self.core.courses.parent_index().get(child_element.name)
        if not parent:
            return

        siblings = list(getattr(parent, "has_module", []) or []) + list(
            getattr(parent, "contains_activity", []) or []
        )
        required_siblings = [c for c in siblings if get_owl_prop(c, "is_mandatory", True)]

        for child in required_siblings:
            child_record = self.core.progress.find_record(student, child)
            if child_record is None:
                return
            status = status_value_from_individual(getattr(child_record, "has_status", None))
            if status != ProgressStatus.COMPLETED.value:
                return

        logger.info("Контейнер %s закрыт автоматически: все обязательные элементы завершены", parent.name)
        update_callback(student.name, parent.name, ProgressStatus.COMPLETED)
