"""Приём событий прогресса + запуск reasoning + каскадный rollup (UC-5).

По DSL §37 + стрелкам §97–§100: ProgressService — оркестратор UC-5. Фактическую
запись в ABox делает через OntologyCore, reasoning — через ReasoningOrchestrator,
каскадное roll-up — через RollupService, инвалидацию кэша — через AccessService.
Зависимости инжектятся явно, Service Locator из OntologyCore убран (решение 23.04).
"""
from __future__ import annotations

import logging
from typing import Any

from core.enums import ProgressStatus
from schemas.schemas import ProgressEvent
from services.access import AccessService
from services.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator
from services.rollup_service import RollupService

logger = logging.getLogger(__name__)


class ProgressService:
    """Оркестратор UC-5: событие прогресса → ABox → reasoning → rollup → cache."""

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
        """Записать событие, запустить Pellet, обновить кэш."""
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
        if event_type in {ProgressStatus.COMPLETED.value, "completed"}:
            progress_record.has_status = [self.core.progress.get_owl_status("completed")]
        elif event_type in {ProgressStatus.FAILED.value, "failed"}:
            progress_record.has_status = [self.core.progress.get_owl_status("failed")]

        if event_data.grade is not None:
            progress_record.has_grade = [float(event_data.grade)]

        self.core.save()

        logger.info("Запуск Pellet Reasoner для студента %s...", student_node_id)
        self.reasoner.reason()
        logger.info("Ризонинг завершён.")

        return self.invalidate_student_cache(event_data.student_id)

    def invalidate_student_cache(self, student_id: str) -> dict:
        """Пересобрать кэш доступа для студента через AccessService."""
        return self.access.rebuild_student_access(student_id)

    def get_student_access(self, student_id: str, course_id: str) -> dict:
        """Матрица доступных элементов в рамках курса (через AccessService)."""
        return self.access.get_course_access(student_id, course_id)

    def update_progress(self, student_id: str, element_id: str, status: Any) -> None:
        """Обновить прогресс студента с поддержкой roll-up."""
        element = self.core.courses.find_by_id(element_id)
        if not element:
            raise ValueError(f"Элемент с ID {element_id} не найден.")

        student = self.core.students.get_or_create(student_id)

        record = self.core.progress.find_record(student, element)
        if not record:
            record = self.core.progress.create_record(student, element)

        val = status if isinstance(status, str) else status.value
        owl_status = self.core.progress.get_owl_status(val)
        statuses = [owl_status] if owl_status else []
        if val == ProgressStatus.COMPLETED.value or val == "completed":
            viewed_status = self.core.progress.get_owl_status("viewed")
            if viewed_status:
                statuses.append(viewed_status)

        record.has_status = statuses
        self.core.save()
        logger.info("Статус %s для %s обновлён до %s", element_id, student.name, val)

        if val == ProgressStatus.COMPLETED.value or val == "completed":
            self.rollup.execute(student, element, self.update_progress)

    def rerun_reasoning_and_rebuild_cache(self, student_id: str) -> None:
        """Фоновая задача после webhook: reason() + rebuild cache."""
        self.reasoner.reason()
        self.invalidate_student_cache(student_id)
