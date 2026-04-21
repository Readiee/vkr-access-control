import logging
import uuid
from typing import List, Optional, Any
from schemas.schemas import ProgressEvent
from core.enums import ProgressStatus
from services.ontology_core import OntologyCore
from services.rollup_service import RollupService
from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)

class ProgressService:
    """Сервис управления прогрессом студентов и логическим выводом доступа."""

    def __init__(self, core: OntologyCore) -> None:
        self.core = core
        self.rollup_service = RollupService(self.core)

    def register_progress(self, event_data: ProgressEvent) -> dict:
        """Записывает факт успеваемости, запускает Pellet и кэширует результат в Redis."""
        student_node_id = f"student_{event_data.student_id}"
        student = self.core.students.get_or_create(student_node_id)

        elem = self.core.courses.find_by_id(event_data.element_id)
        if not elem:
            raise ValueError(
                f"Элемент {event_data.element_id} не найден. Сначала выполните синхронизацию курса."
            )

        progress_record = self.core.progress.create_record(student, elem)

        if event_data.event_type == ProgressStatus.COMPLETED.value or event_data.event_type == "completed":
            progress_record.has_status = [self.core.progress.get_owl_status("completed")]
        elif event_data.event_type == ProgressStatus.FAILED.value or event_data.event_type == "failed":
            progress_record.has_status = [self.core.progress.get_owl_status("failed")]

        if event_data.grade is not None:
            progress_record.has_grade = [float(event_data.grade)]


        self.core.save()

        logger.info("Запуск Pellet Reasoner для студента %s...", student_node_id)
        self.core.run_reasoner()
        logger.info("Ризонинг завершён.")

        return self.invalidate_student_cache(event_data.student_id)

    def invalidate_student_cache(self, student_id: str) -> dict:
        """Сбор результатов вывода и прогон через пайплайн обогатителей.
        Обновляет кэш в Redis.
        """
        student_node_id = student_id if student_id.startswith("student_") else f"student_{student_id}"
        student = self.core.courses.find_by_id(student_node_id)
        if not student:
            return {"status": "error", "message": f"Студент {student_id} не найден."}

        from utils.access_postprocessors import DateWindowPostProcessor
        postprocessors = [DateWindowPostProcessor()]
        inferred_access: dict = {}

        for course_elem in self.core.courses.get_all_elements():
            all_policies = getattr(course_elem, "has_access_policy", [])
            active_policies = [p for p in all_policies if get_owl_prop(p, "is_active", True) is True]
            
            parent_unlocked = True
            parents = []
            
            for p in self.core.courses.get_all_elements():
                if course_elem in (getattr(p, "has_module", []) + getattr(p, "contains_element", [])):
                    parents.append(p)
                    break

            for p in parents:
                p_active = [pol for pol in getattr(p, "has_access_policy", []) if get_owl_prop(pol, "is_active", True) is True]
                if p_active and student not in getattr(p, "is_available_for", []):
                    parent_unlocked = False
                    break

            swrl_passed = (not active_policies) or (student in getattr(course_elem, "is_available_for", []))
            
            is_available = parent_unlocked and swrl_passed
            
            if is_available:
                element_data: dict = {}
                for pp in postprocessors:
                    element_data = pp.process(course_elem, element_data)
                inferred_access[course_elem.name] = element_data

        self.core.cache.set_student_access(student_id, inferred_access)

        return {
            "student_id": student_id,
            "inferred_available_elements": list(inferred_access.keys()),
        }

    def get_student_access(self, student_id: str, course_id: str) -> dict:
        """Мгновенно возвращает доступные элементы, прогоняя кэш через конвейер фильтров."""
        
        cached_access = self.core.cache.get_student_access(student_id)
        
        if cached_access is None:
            import logging
            logging.getLogger(__name__).info(f"Кэш для {student_id} пуст. Запуск ленивого пересчета...")
            self.invalidate_student_cache(student_id)
            cached_access = self.core.cache.get_student_access(student_id)
            if cached_access is None:
                return {"available_elements": []}

        inferred_access = cached_access
        
        from utils.access_postprocessors import DateWindowFilter
        access_filters = [DateWindowFilter()]
        
        filtered_access = {}
        for elem_id, elem_data in inferred_access.items():
            is_valid = True
            for f in access_filters:
                if not f.is_valid(elem_data):
                    is_valid = False
                    break
            if is_valid:
                filtered_access[elem_id] = elem_data

        course_elements = self._get_course_elements(course_id)
        
        parent_map = {}
        for el in self.core.courses.get_all_elements():
            children = getattr(el, "has_module", []) + getattr(el, "contains_element", [])
            for c in children:
                parent_map[c.name] = el.name

        valid_elements = set()
        
        # Рекурсивная функция: элемент доступен только если доступны все его родители
        def is_really_available(eid):
            if eid not in filtered_access: 
                return False
            parent_id = parent_map.get(eid)
            if parent_id:
                return is_really_available(parent_id)
            return True

        for eid in course_elements:
            if is_really_available(eid):
                valid_elements.add(eid)

        return {"available_elements": list(valid_elements)}

    def _get_course_elements(self, course_id: str) -> set:
        """Рекурсивно собирает все ID элементов, принадлежащих курсу."""
        course = self.core.courses.find_by_id(course_id)
        if not course:
            return set()
            
        elements = {course.name}
        
        def collect(node):
            for m in getattr(node, "has_module", []):
                elements.add(m.name)
                collect(m)
            for e in getattr(node, "contains_element", []):
                elements.add(e.name)
                collect(e)
                
        collect(course)
        return elements

    def update_progress(self, student_id: str, element_id: str, status: ProgressStatus) -> None:
        """Обновляет прогресс студента по элементу с поддержкой Roll-up."""
        element = self.core.courses.find_by_id(element_id)
        if not element:
            raise ValueError(f"Элемент с ID {element_id} не найден.")

        student = self.core.students.get_or_create(student_id)

        record = self.core.progress.find_record(student, element)
        if not record:
            record = self.core.progress.create_record(student, element)

        # Маппинг в OWL-индивиды
        if isinstance(status, str):
            val = status
        else:
            val = status.value
            
        owl_status = self.core.progress.get_owl_status(val)
        statuses = [owl_status] if owl_status else []
        
        # 'completed' включает в себя 'viewed'
        if val == "completed" or val == ProgressStatus.COMPLETED.value:
            viewed_status = self.core.progress.get_owl_status("viewed")
            if viewed_status:
                statuses.append(viewed_status)
                
        record.has_status = statuses
        
        self.core.save()
        logger.info(f"Статус {element_id} для {student.name} обновлен до {status}")

        if status == ProgressStatus.COMPLETED.value or getattr(status, 'value', None) == ProgressStatus.COMPLETED.value:
            self.rollup_service.execute(student, element, self.update_progress)


