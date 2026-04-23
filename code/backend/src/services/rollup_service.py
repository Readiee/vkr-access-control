import logging
from typing import Callable
from core.enums import ProgressStatus
from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)

class RollupService:
    """Сервис для автоматического 'подъема' статуса завершения по иерархии курса."""
    
    def __init__(self, core):
        self.core = core

    def execute(self, student, child_element, update_callback: Callable[[str, str, ProgressStatus], None]) -> None:
        """
        Проверяет, завершены ли все обязательные соседи элемента.
        Если да, вызывает update_callback для автоматического завершения родителя.
        """
        parent = None
        # Поиск родителя
        for p in self.core.courses.get_all_elements():
            children = getattr(p, "has_module", []) + getattr(p, "contains_activity", [])
            if child_element in children:
                parent = p
                break
                
        if not parent:
            return
            
        # Сбор обязательных соседей
        siblings = getattr(parent, "has_module", []) + getattr(parent, "contains_activity", [])
        required_siblings = []
        for child in siblings:
            if get_owl_prop(child, "is_mandatory", True):
                required_siblings.append(child)
                
        # Проверка статусов всех обязательных соседей
        all_completed = True
        for child in required_siblings:
            child_record = self.core.progress.find_record(student, child)
            if not child_record:
                all_completed = False
                break
                
            status_obj = getattr(child_record, "has_status", None)
            if status_obj is None:
                all_completed = False
                break
            current_status_str = status_obj.name.replace("status_", "") if hasattr(status_obj, "name") else str(status_obj)
                
            if current_status_str != ProgressStatus.COMPLETED.value:
                all_completed = False
                break
                
        # Если всё сдано - рекурсивно завершаем родителя через callback
        if all_completed:
            logger.info(f"Roll-up: Все элементы {parent.name} завершены. Автоматическое закрытие родителя.")
            update_callback(student.name, parent.name, ProgressStatus.COMPLETED)
