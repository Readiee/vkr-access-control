from __future__ import annotations

import logging
from typing import Any

from core.enums import ProgressStatus
from services.access import AccessService
from services.ontology_core import OntologyCore
from services.progress_service import ProgressService
from services.reasoning import ReasoningOrchestrator
from utils.owl_utils import label_or_name

logger = logging.getLogger(__name__)

SANDBOX_STUDENT_ID = "student_sandbox"


class SandboxService:
    """Песочница методиста: симуляция прогресса на тестовом студенте

    Работает с единственным SandboxStudent: методист дёргает один и тот же
    профиль для проверки правил. Пул тестовых студентов убран — смысл симулятора
    в быстрой проверке правила, а не в репрезентативной выборке
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
        # Перезачёт компетенций методистом. Вспомогательное SWRL-правило
        # выводит компетенции из ProgressRecord, но OWL монотонен — убрать
        # их без очистки нельзя. Перед каждым прогоном перезаписываем
        # has_competency на manual; резонер допишет inferred из актуального
        # прогресса. In-memory: рестарт uvicorn теряет manual-override
        self._manual_competencies: dict[str, list[str]] = {}

    def _sandbox_student(self):
        """Единственный sandbox-студент; создаёт индивида, если его ещё нет"""
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

        groups = list(getattr(student, "belongs_to_group", []) or [])
        group_ids = [g.name for g in groups]
        group_names = [label_or_name(g) for g in groups]

        return {
            "student_id": sandbox_user_id,
            "student_name": label_or_name(student) or sandbox_user_id,
            "available_elements": available_elements,
            "progress": progress_dict,
            "active_competencies": active_comps,
            "group_ids": group_ids,
            "group_names": group_names,
        }

    def _cascade_delete_parent_records(self, student, element):
        parent_index = self.core.courses.parent_index()
        node = element
        while True:
            parent = parent_index.get(node.name)
            if parent is None:
                return
            parent_record = self.core.progress.find_record(student, parent)
            if parent_record is None:
                return
            self.core.progress.delete_record(student, parent_record)
            node = parent

    def simulate_progress(self, payload) -> dict:
        student = self._sandbox_student()
        sandbox_user_id = student.name

        # Даунгрейд (viewed/failed): сносим родительские рекорды, чтобы агрегация пересчитала их
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

        self._reset_competencies_to_manual(student)
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
        self._reset_competencies_to_manual(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": f"Откат {element_id} завершен"}

    def _clear_inferred_access(self, student):
        """Чистит выведенные доступы, чтобы резонер собрал их заново (OWL монотонен)"""
        for elem in self.core.courses.get_all_elements():
            if student in getattr(elem, "is_available_for", []):
                elem.is_available_for.remove(student)

    def _reset_competencies_to_manual(self, student) -> None:
        """Откат has_competency к перезачёту методиста

        Вспомогательное SWRL-правило выводит компетенции из ProgressRecord,
        но OWL монотонен и отзыв prerequisite сам по себе не удаляет ранее
        выведенный has_competency. Перед каждым прогоном перезаписываем
        has_competency на то, что задал методист вручную через set_competencies;
        дальше резонер допишет выводы из актуального прогресса
        """
        comp_cls = getattr(self.core.onto, "Competency", None)
        manual_ids = self._manual_competencies.get(student.name, [])
        manual: list = []
        if comp_cls is not None:
            for cid in manual_ids:
                comp = self.core.onto.search_one(type=comp_cls, iri=f"*{cid}")
                if comp is not None:
                    manual.append(comp)
        student.has_competency = manual

    def reset_all(self) -> dict:
        student = self._sandbox_student()

        self._manual_competencies.pop(student.name, None)
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
        # Валидируем, что все id — действительно Competency. Некорректные
        # id игнорируем молча: фронт не должен их слать, это просто защита
        valid_ids: list[str] = []
        if comp_cls is not None:
            for cid in competency_ids:
                comp = self.core.onto.search_one(type=comp_cls, iri=f"*{cid}")
                if comp is not None:
                    valid_ids.append(cid)
        self._manual_competencies[student.name] = valid_ids

        self._reset_competencies_to_manual(student)
        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": "Компетенции обновлены"}

    def set_groups(self, group_ids: list[str]) -> dict:
        """Перезаписать набор групп sandbox-студента; пустой список — снять все

        Студент может состоять в нескольких группах (поток + проектная команда).
        Дубликаты игнорируются, неизвестные id поднимают ValueError
        """
        student = self._sandbox_student()
        group_cls = getattr(self.core.onto, "Group", None)

        unique_ids: list[str] = []
        seen: set[str] = set()
        for gid in group_ids or []:
            if gid and gid not in seen:
                seen.add(gid)
                unique_ids.append(gid)

        groups = []
        if unique_ids and group_cls is not None:
            for gid in unique_ids:
                group = self.core.onto.search_one(type=group_cls, iri=f"*{gid}")
                if group is None:
                    raise ValueError(f"Группа {gid} не найдена.")
                groups.append(group)

        student.belongs_to_group = groups

        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {
            "status": "success",
            "message": "Группы обновлены" if groups else "Группы сняты",
        }
