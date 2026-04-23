from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.enums import ProgressStatus
from services.access import AccessService
from services.ontology_core import OntologyCore
from services.progress_service import ProgressService
from services.reasoning import ReasoningOrchestrator

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_ID = "sandbox_new"


class SandboxService:
    """Песочница методиста (UC-7a/b/c).

    По DSL §38 + §110–§111: SandboxService работает с ABox через OntologyCore,
    пересчитывает reasoning через ReasoningOrchestrator и переиспользует
    AccessService для чтения карты доступа. Запись прогресса и roll-up —
    через ProgressService (разрешённое исключение слоистости — DSL §117).
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

    def list_sandbox_students(self) -> List[Dict[str, str]]:
        """Все индивиды класса SandboxStudent — для выбора в UI."""
        cls = getattr(self.core.onto, "SandboxStudent", None)
        if cls is None:
            return []
        result = []
        for s in cls.instances():
            label = s.label[0] if getattr(s, "label", None) else s.name
            result.append({"id": s.name, "name": label})
        return sorted(result, key=lambda x: x["id"])

    def _resolve_student(self, student_id: Optional[str]):
        """Возвращает индивида-песочницу по id. None/пусто → первый доступный.
        Защита: запрещаем трогать НЕ-SandboxStudent (реальных студентов методист
        не должен редактировать через симулятор)."""
        cls = getattr(self.core.onto, "SandboxStudent", None)
        if student_id:
            ind = self.core.onto.search_one(iri=f"*{student_id}")
            if ind is not None and cls is not None and isinstance(ind, cls):
                return ind
            raise ValueError(
                f"Студент {student_id} не является sandbox-студентом — симулятор "
                "не может менять прогресс реальных студентов курса."
            )
        # fallback: любой существующий sandbox, или создаём новый
        instances = list(cls.instances()) if cls else []
        if instances:
            return instances[0]
        student = cls(DEFAULT_SANDBOX_ID) if cls else self.core.students.get_or_create(DEFAULT_SANDBOX_ID)
        return student

    def get_sandbox_state(self, course_id: str, student_id: Optional[str] = None) -> dict:
        """Получает состояние песочницы (доступы и прогресс)"""
        student = self._resolve_student(student_id)
        sandbox_user_id = student.name

        access_data = self.access.get_course_access(sandbox_user_id, course_id)
        available_elements = access_data.get("available_elements", [])

        # 2. Получаем текущий прогресс
        progress_dict = {}
        records = self.core.progress.find_all_for_student(student)
        for r in records:
            element_id = r.refers_to_element[0].name if getattr(r, "refers_to_element", []) else None
            # ДОБАВЛЕНО: Поиск приоритетного статуса (completed важнее viewed)
            status = None
            for s in getattr(r, "has_status", []):
                s_name = s.name.replace("status_", "")
                if s_name == "completed":
                    status = "completed"
                    break
                status = s_name
                
            grade = r.has_grade[0] if getattr(r, "has_grade", []) else None
            
            if element_id and status:
                progress_dict[element_id] = {
                    "status": status,
                    "grade": grade
                }

        # 3. Получаем активные компетенции
        active_comps = []
        for comp in getattr(student, "has_competency", []):
            active_comps.append(comp.name)

        return {
            "student_id": sandbox_user_id,
            "student_name": student.label[0] if getattr(student, "label", None) else sandbox_user_id,
            "available_elements": available_elements,
            "progress": progress_dict,
            "active_competencies": active_comps,
        }

    def _cascade_delete_parent_records(self, student, element):
        for p in self.core.courses.get_all_elements():
            children = getattr(p, "has_module", []) + getattr(p, "contains_element", [])
            if element in children:
                parent_record = self.core.progress.find_record(student, p)
                if parent_record:
                    self.core.progress.delete_record(student, parent_record)
                    # Рекурсивно идем выше
                    self._cascade_delete_parent_records(student, p)

    def simulate_progress(self, payload, student_id: Optional[str] = None) -> dict:
        """Эмулирует прохождение элемента"""
        student = self._resolve_student(student_id)
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
                record.has_grade = [payload.grade]
                self.core.save()

        self.reasoner.reason()
        self.access.rebuild_student_access(sandbox_user_id)
        return {"status": "success", "message": f"Прогресс для {payload.element_id} обновлен"}

    def rollback_progress(self, element_id: str, student_id: Optional[str] = None) -> dict:
        """'Скальпель': удаляет ProgressRecord конкретного элемента и его родителей (откат Roll-up)"""
        student = self._resolve_student(student_id)
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
        """Удаляет все выведенные доступы, чтобы ризонер собрал их заново (фикс монотонности)."""
        for elem in self.core.courses.get_all_elements():
            if student in getattr(elem, "is_available_for", []):
                elem.is_available_for.remove(student)

    def reset_all(self, student_id: Optional[str] = None) -> dict:
        """'Ядерная кнопка': удаляет все ProgressRecord и компетенции студента"""
        student = self._resolve_student(student_id)

        student.has_competency = []
        records = self.core.progress.find_all_for_student(student)
        for r in records:
            self.core.progress.delete_record(student, r)

        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": "Песочница полностью очищена"}

    def set_competencies(self, competency_ids: list[str], student_id: Optional[str] = None) -> dict:
        """Перезаписывает весь список компетенций студента и обновляет граф."""
        student = self._resolve_student(student_id)
        student.has_competency = []
        for cid in competency_ids:
            comp = self.core.courses.find_by_id(cid)
            if comp:
                student.has_competency.append(comp)

        self._clear_inferred_access(student)
        self.core.save()
        self.reasoner.reason()
        self.access.rebuild_student_access(student.name)
        return {"status": "success", "message": "Компетенции обновлены"}
