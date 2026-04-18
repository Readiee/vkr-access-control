from core.enums import ProgressStatus
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SandboxService:
    def __init__(self, core, progress_service):
        self.core = core
        self.progress_service = progress_service
        self.sandbox_user_id = "student_sandbox"

    def _get_sandbox_student(self):
        """Получает или создает тестового студента"""
        student = self.core.students.get_or_create(self.sandbox_user_id)
        return student

    def get_sandbox_state(self, course_id: str) -> dict:
        """Получает состояние песочницы (доступы и прогресс)"""
        student = self._get_sandbox_student()
        
        # Получение доступных элементов из кэша (или напрямую из progress_service)
        access_data = self.progress_service.get_student_access(self.sandbox_user_id, course_id)
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
            "available_elements": available_elements,
            "progress": progress_dict,
            "active_competencies": active_comps
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

    def simulate_progress(self, payload) -> dict:
        """Эмулирует прохождение элемента"""
        # Если это даунгрейд (viewed/failed), сносим родительские рекорды, чтобы Roll-up пересчитал их потом
        if payload.status != ProgressStatus.COMPLETED.value and payload.status != "completed":
            student = self._get_sandbox_student()
            element = self.core.courses.find_by_id(payload.element_id)
            if element:
                self._cascade_delete_parent_records(student, element)
                self._clear_inferred_access(student)
                
        self.progress_service.update_progress(self.sandbox_user_id, payload.element_id, payload.status)
        # Добавляем оценку, если есть
        if payload.grade is not None:
            student = self._get_sandbox_student()
            element = self.core.courses.find_by_id(payload.element_id)
            record = self.core.progress.find_record(student, element)
            if record:
                record.has_grade = [payload.grade]
                self.core.save()
                
        self.core.run_reasoner()
        self.progress_service.invalidate_student_cache(self.sandbox_user_id)
        return {"status": "success", "message": f"Прогресс для {payload.element_id} обновлен"}

    def rollback_progress(self, element_id: str) -> dict:
        """'Скальпель': удаляет ProgressRecord конкретного элемента и его родителей (откат Roll-up)"""
        student = self._get_sandbox_student()
        element = self.core.courses.find_by_id(element_id)
        if not element:
            raise ValueError(f"Элемент {element_id} не найден")

        # Поиск записи элемента
        record = self.core.progress.find_record(student, element)
        self.core.progress.delete_record(student, record)

        self._cascade_delete_parent_records(student, element)
        self._clear_inferred_access(student)
        self.core.save()
        self.core.run_reasoner()
        self.progress_service.invalidate_student_cache(self.sandbox_user_id)
        return {"status": "success", "message": f"Откат {element_id} завершен"}

    def _clear_inferred_access(self, student):
        """Удаляет все выведенные доступы, чтобы ризонер собрал их заново (фикс монотонности)."""
        for elem in self.core.courses.get_all_elements():
            if student in getattr(elem, "is_available_for", []):
                elem.is_available_for.remove(student)

    def reset_all(self) -> dict:
        """'Ядерная кнопка': удаляет все ProgressRecord и компетенции студента"""
        student = self._get_sandbox_student()
        
        # Удаление компетенции
        student.has_competency = []
        
        # Удаление прогресса
        records = self.core.progress.find_all_for_student(student)
        for r in records:
            self.core.progress.delete_record(student, r)
            
        self._clear_inferred_access(student)
        self.core.save()
        self.core.run_reasoner()
        self.progress_service.invalidate_student_cache(self.sandbox_user_id)
        return {"status": "success", "message": "Песочница полностью очищена"}

    def set_competencies(self, competency_ids: list[str]) -> dict:
        """Перезаписывает весь список компетенций студента и обновляет граф."""
        student = self._get_sandbox_student()
        
        student.has_competency = []
        
        for cid in competency_ids:
            comp = self.core.courses.find_by_id(cid)
            if comp:
                student.has_competency.append(comp)
                
        # Очистка старых выводов перед ризонером
        self._clear_inferred_access(student)
        
        self.core.save()
        self.core.run_reasoner()
        self.progress_service.invalidate_student_cache(self.sandbox_user_id)
        return {"status": "success", "message": "Компетенции обновлены"}
