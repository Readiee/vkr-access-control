from __future__ import annotations

from typing import Any

from core.enums import ProgressStatus
from schemas import ProgressEvent
from services.access import AccessService
from services.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator
from services.rollup_service import RollupService


class ProgressService:
    """Регистрация прогресса студента: запись в ABox, прогон резонера, rollup и сброс кэша."""

    def __init__(
        self,
        core: OntologyCore,
        *,
        reasoner: ReasoningOrchestrator,
        rollup: RollupService,
        access: AccessService,
    ) -> None:
        self.core = core
        self.reasoner = reasoner
        self.rollup = rollup
        self.access = access

    def register_progress(self, event_data: ProgressEvent) -> dict:
        student_node_id = f"student_{event_data.student_id}"
        student = self.core.students.get_or_create(student_node_id)

        elem = self.core.courses.find_by_id(event_data.element_id)
        if not elem:
            raise ValueError(
                f"Элемент {event_data.element_id} не найден. Сначала выполните синхронизацию курса."
            )

        progress_record = self.core.progress.create_record(student, elem)
        event_type = (
            event_data.event_type.value
            if hasattr(event_data.event_type, "value")
            else event_data.event_type
        )
        if event_type == ProgressStatus.COMPLETED.value:
            progress_record.has_status = self.core.progress.get_owl_status(ProgressStatus.COMPLETED)
        elif event_type == ProgressStatus.FAILED.value:
            progress_record.has_status = self.core.progress.get_owl_status(ProgressStatus.FAILED)

        if event_data.grade is not None:
            progress_record.has_grade = float(event_data.grade)

        self.core.save()
        self.reasoner.reason()
        return self.invalidate_student_cache(event_data.student_id)

    def invalidate_student_cache(self, student_id: str) -> dict:
        return self.access.rebuild_student_access(student_id)

    def get_student_access(self, student_id: str, course_id: str) -> dict:
        return self.access.get_course_access(student_id, course_id)

    def update_progress(self, student_id: str, element_id: str, status: Any) -> None:
        element = self.core.courses.find_by_id(element_id)
        if not element:
            raise ValueError(f"Элемент с ID {element_id} не найден.")

        student = self.core.students.get_or_create(student_id)

        record = self.core.progress.find_record(student, element)
        if not record:
            record = self.core.progress.create_record(student, element)

        val = status if isinstance(status, str) else status.value
        # has_status — functional; completed покрывает viewed вспомогательным SWRL-правилом
        record.has_status = self.core.progress.get_owl_status(val)
        self.core.save()

        if val == ProgressStatus.COMPLETED.value:
            self.rollup.execute(student, element, self.update_progress)

    def rerun_reasoning_and_rebuild_cache(self, student_id: str) -> None:
        self.reasoner.reason()
        self.invalidate_student_cache(student_id)
