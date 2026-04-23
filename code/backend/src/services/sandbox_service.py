from __future__ import annotations

import logging
from typing import Any

from core.enums import ProgressStatus
from services.access import AccessService
from services.ontology_core import OntologyCore
from services.progress_service import ProgressService
from services.reasoning import ReasoningOrchestrator

logger = logging.getLogger(__name__)

SANDBOX_STUDENT_ID = "student_sandbox"


class SandboxService:
    """Песочница методиста (UC-7a/b/c).

    Работает с единственным SandboxStudent-ом: методист дёргает один и тот же
    профиль для проверки правил. Пул тестовых студентов убран — смысл
    симулятора в быстрой проверке правила, а не в репрезентативной выборке.
    """

    def __init__(
        self,
        core: OntologyCore,
        *,
        reasoner: ReasoningOrchestrator,
        access: AccessService,
        progress: ProgressService,
    ) -> None:
        self.core = core
        self.reasoner = reasoner
        self.access = access
        self.progress = progress

    def _sandbox_student(self):
        """Единственный sandbox-студент. Создаёт индивида, если его ещё нет."""
        cls = getattr(self.core.onto, "SandboxStudent", None)
        if cls is None:
            return self.core.students.get_or_create(SANDBOX_STUDENT_ID)
        existing = self.core.onto.search_one(type=cls, iri=f"*{SANDBOX_STUDENT_ID}")
        if existing is not None:
            return existing
        student = cls(SANDBOX_STUDENT_ID)
        student.label = ["Песочница"]
        return student

    def get_sandbox_state(self, course_id: str) -> dict:
        student = self._sandbox_student()
        sandbox_user_id = student.name

        access_data = self.access.get_course_access(sandbox_user_id, course_id)
        available_elements = access_data.get("available_elements", [])

        progress_dict: dict[str, dict[str, Any]] = {}
        records = self.core.progress.find_all_for_student(student)
        for r in records:
            element_id = r.refers_to_element.name if getattr(r, "refers_to_element", None) else None
            status_obj = getattr(r, "has_status", None)
            status = status_obj.name.replace("status_", "") if status_obj is not None else None

            grade = r.has_grade if getattr(r, "has_grade", None) is not None else None

            if element_id and status:
                progress_dict[element_id] = {
                    "status": status,
                    "grade": grade,
                }

        active_comps = [comp.name for comp in getattr(student, "has_competency", [])]

        group = next(iter(getattr(student, "belongs_to_group", []) or []), None)

        return {
            "student_id": sandbox_user_id,
            "student_name": student.label[0] if getattr(student, "label", None) else sandbox_user_id,
            "available_elements": available_elements,
            "progress": progress_dict,
            "active_competencies": active_comps,
            "group_id": group.name if group else None,
            "group_name": (group.label[0] if getattr(group, "label", None) else group.name) if group else None,
        }

    def _cascade_delete_parent_records(self, student, element):
        for p in self.core.courses.get_all_elements():
            children = getattr(p, "has_module", []) + getattr(p, "contains_activity", [])
            if element in children:
                parent_record = self.core.progress.find_record(student, p)
                if parent_record:
                    self.core.progress.delete_record(student, parent_record)
                    self._cascade_delete_parent_records(student, p)

    def simulate_progress(self, payload) -> dict:
        student = self._sandbox_student()
        sandbox_user_id = student.name

        # Даунгрейд (viewed/failed) — сносим родительские рекорды, чтобы Roll-up пересчитал их
        if payload.status != ProgressStatus.COMPLETED.value and payload.status != "completed":
            element = self.core.courses.find_by_id(payload.element_id)
            if element:
                self._cascade_delete_parent_records(student, element)
                self._clear_inferred_access(student)

        self.progress.update_progress(sandbox_user_id, payload.element_id, payload.status)
        if payload.grade is not None:
            element = self.core.courses.find_by_id(payload.element_id)
            record = self.core.progress.find_record(student, element)
            if record:
                record.has_grade = payload.grade
                self.core.save()

        self.reasoner.reason()
        self.access.rebuild_student_access(sandbox_user_id)
        return {"status": "success", "message": f"Прогресс для {payload.element_id} обновлен"}

    def rollback_progress(self, element_id: str) -> dict:
        student = self._sandbox_student()
        element = self.core.courses.find_by_id(element_id)
        if not element:
            raise ValueError(f"Элемент {element_id} не найден")

        record = self.core.progress.find_record(student, element)
        self.core.progress.delete_record(student, record)

        self._cascade_delete_parent_records(student, element)
        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": f"Откат {element_id} завершен"}

    def _clear_inferred_access(self, student):
        """Чистит выведенные доступы, чтобы ризонер собрал их заново (OWL монотонен)."""
        for elem in self.core.courses.get_all_elements():
            if student in getattr(elem, "is_available_for", []):
                elem.is_available_for.remove(student)

    def reset_all(self) -> dict:
        student = self._sandbox_student()

        student.has_competency = []
        records = self.core.progress.find_all_for_student(student)
        for r in records:
            self.core.progress.delete_record(student, r)

        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": "Песочница полностью очищена"}

    def set_competencies(self, competency_ids: list[str]) -> dict:
        student = self._sandbox_student()
        comp_cls = getattr(self.core.onto, "Competency", None)
        student.has_competency = []
        if comp_cls is not None:
            for cid in competency_ids:
                # Competency — самостоятельный класс (не CourseStructure),
                # поэтому courses.find_by_id его не находит.
                comp = self.core.onto.search_one(type=comp_cls, iri=f"*{cid}")
                if comp is not None:
                    student.has_competency.append(comp)

        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": "Компетенции обновлены"}

    def set_group(self, group_id: str | None) -> dict:
        """Перезаписывает единственную группу у sandbox-студента. None → снять.

        Для симулятора группа одна, но ObjectProperty non-functional, потому
        присваиваем список из 0/1 элемента.
        """
        student = self._sandbox_student()
        if group_id:
            group_cls = getattr(self.core.onto, "Group", None)
            group = None
            if group_cls is not None:
                group = self.core.onto.search_one(type=group_cls, iri=f"*{group_id}")
            if group is None:
                raise ValueError(f"Группа {group_id} не найдена.")
            student.belongs_to_group = [group]
        else:
            student.belongs_to_group = []

        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": "Группа обновлена" if group_id else "Группа снята"}
