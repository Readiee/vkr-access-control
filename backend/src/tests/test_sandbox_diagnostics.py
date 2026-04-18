import logging
import json
import sys
import os

# Добавляем корень src в путь, чтобы импорты работали
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ontology_core import OntologyCore
from services.progress_service import ProgressService
from services.sandbox_service import SandboxService
from core.enums import ProgressStatus

# Настройка подробного логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("DIAGNOSTICS")

def run_diagnostics():
    logger.info("=== СТАРТ ДИАГНОСТИКИ СИМУЛЯТОРА ===")
    
    # 1. Инициализация (используем демо-базу, чтобы не портить основную)
    # Используем абсолютный путь для надежности
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    onto_path = os.path.join(base_dir, "onto", "ontologies", "demo_knowledge_base.owl")
    
    logger.info(f"Загрузка онтологии: {onto_path}")
    
    core = OntologyCore(onto_path=onto_path)
    progress_service = ProgressService(core)
    sandbox_service = SandboxService(core, progress_service)
    
    # Сбрасываем Песочницу перед тестом
    logger.info("Сброс песочницы...")
    sandbox_service.reset_all()
    
    # 2. ТЕСТ 1: Базовая блокировка и транзитивность
    logger.info("--- ТЕСТ 1: Проверка изначальных доступов и транзитивности ---")
    # В демо-базе course_python_basics -> module_2_advanced (заблокирован политикой)
    state = sandbox_service.get_sandbox_state("course_python_basics")
    avail = state.get("available_elements", [])
    
    logger.info(f"Доступные элементы: {avail}")
    if "module_2_advanced" in avail:
        logger.error(" ПРОВАЛ: module_2_advanced доступен, хотя на нем висит политика!")
    else:
        logger.info(" ОК: module_2_advanced заблокирован.")
        
    # 3. ТЕСТ 2: Выполнение условия политики (Сдача теста)
    logger.info("--- ТЕСТ 2: Эмуляция прохождения (разблокировка) ---")
    # Политика на module_2_advanced требует сдачи test_1_syntax на >= 75
    class MockPayload:
        element_id = "test_1_syntax"
        status = ProgressStatus.COMPLETED
        grade = 85.0
        
    sandbox_service.simulate_progress(MockPayload())
    
    state_after = sandbox_service.get_sandbox_state("course_python_basics")
    avail_after = state_after.get("available_elements", [])
    logger.info(f"Доступные элементы после сдачи: {avail_after}")
    
    if "module_2_advanced" not in avail_after:
        logger.error(" ПРОВАЛ: module_2_advanced не открылся после сдачи теста! (Проблема SWRL или типов данных)")
        # Диагностика почему не сработало:
        pr = core.onto.search_one(type=core.onto.ProgressRecord, refers_to_element=core.onto.test_1_syntax)
        if pr:
            logger.info(f"Дамп прогресса: Статус={getattr(pr, 'has_status', [])}, Оценка={getattr(pr, 'has_grade', [])}")
        else:
            logger.info("Дамп прогресса: Прогресс не найден!")
    else:
        logger.info(" ОК: module_2_advanced успешно разблокирован.")

    # 4. ТЕСТ 3: Отключение политики (is_active = False)
    logger.info("--- ТЕСТ 3: Проверка отключения политики ---")
    sandbox_service.rollback_progress("test_1_syntax") # Откатываем прогресс, модуль должен снова закрыться
    
    # Выключаем политику (ищем по IRI фрагменту или rdfs:label)
    # В демо-базе политика может иметь другое имя
    policy = core.onto.search_one(iri="*policy*module2*")
    if policy:
        logger.info(f"Найдена политика: {policy.name}")
        policy.is_active = [False]
        core.save()
        core.run_reasoner()
        # Мы не можем вызвать invalidate_student_cache так как это метод в progress_service
        # и он должен быть вызван явно если мы хотим обновить кэш. 
        # Sandbox service обычно делает это внутри своих методов.
        progress_service.invalidate_student_cache("student_sandbox")
        
        state_disabled = sandbox_service.get_sandbox_state("course_python_basics")
        if "module_2_advanced" not in state_disabled.get("available_elements", []):
            logger.error(" ПРОВАЛ: module_2_advanced остался закрытым при is_active=False! (SWRL игнорирует флаг)")
        else:
            logger.info(" ОК: Модуль открылся при отключенной политике.")
    else:
        logger.warning("Политика для module_2_advanced не найдена для тестирования отключения.")

    logger.info("=== ДИАГНОСТИКА ЗАВЕРШЕНА ===")

if __name__ == "__main__":
    run_diagnostics()
