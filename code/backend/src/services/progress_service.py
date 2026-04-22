"""Приём событий прогресса + roll-up статусов.

Чтение матрицы доступа вынесено в AccessService — ProgressService только фиксирует
событие в ABox, запускает reasoning, даёт AccessService пересобрать кэш Redis.
"""
from __future__ import annotations

import logging
from typing import Any

from core.enums import ProgressStatus
from schemas.schemas import ProgressEvent
from services.access_service import AccessService
from services.ontology_core import OntologyCore
from services.rollup_service import RollupService

logger = logging.getLogger(__name__)


class ProgressService:
    """Сервис регистрации прогресса студентов + запуск reasoning."""

    def __init__(self, core: OntologyCore) -> None:
        self.core = core
        self.rollup_service = RollupService(self.core)
        self.access_service = AccessService(self.core)

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
        event_type = event_data.event_type.value if hasattr(event_data.event_type, "value") else event_data.event_type
        if event_type in {ProgressStatus.COMPLETED.value, "completed"}:
            progress_record.has_status = [self.core.progress.get_owl_status("completed")]
        elif event_type in {ProgressStatus.FAILED.value, "failed"}:
            progress_record.has_status = [self.core.progress.get_owl_status("failed")]

        if event_data.grade is not None:
            progress_record.has_grade = [float(event_data.grade)]

        self.core.save()

        logger.info("Запуск Pellet Reasoner для студента %s...", student_node_id)
        self.core.run_reasoner()
        logger.info("Ризонинг завершён.")

        return self.invalidate_student_cache(event_data.student_id)

    def invalidate_student_cache(self, student_id: str) -> dict:
        """Пересобрать кэш доступа для студента через AccessService."""
        return self.access_service.rebuild_student_access(student_id)

    def get_student_access(self, student_id: str, course_id: str) -> dict:
        """Матрица доступных элементов в рамках курса (через AccessService)."""
        return self.access_service.get_course_access(student_id, course_id)

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
            self.rollup_service.execute(student, element, self.update_progress)
