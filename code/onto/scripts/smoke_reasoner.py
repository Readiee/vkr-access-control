"""Автономный сервис запуска Pellet Reasoner.

Загружает demo_knowledge_base.owl, демонстрирует состояние графа
до и после логического вывода: открылся ли module_2_advanced
для student_ivanov после проверки правила grade_required.

Использование:
    python 4_reasoner_service.py
"""
import subprocess
from owlready2 import get_ontology, sync_reasoner_pellet

# Загружаем наполненную базу знаний
onto = get_ontology("file://../ontologies/demo_knowledge_base.owl").load()

with onto:
    student  = onto.search_one(iri="*student_ivanov")
    module_2 = onto.search_one(iri="*module_2_advanced")

    if not student or not module_2:
        print("Ошибка: тестовые данные не найдены. Проверьте скрипт 3_seed_demo_data.py")
        exit(1)

    # ------------------------------------------------------------------
    # Состояние ДО логического вывода
    # ------------------------------------------------------------------
    print("=== ДО ЛОГИЧЕСКОГО ВЫВОДА ===")
    print(f"Доступен ли {module_2.name} для {student.name}? -> {student in module_2.is_available_for}")
    for pr in student.has_progress_record:
        print(f"  Статус {pr.name}: {[s.name for s in pr.has_status]}")

    # ------------------------------------------------------------------
    # Запуск Pellet Reasoner с патчем совместимости Java/Jena
    # ------------------------------------------------------------------
    print("\n[Запуск Pellet Reasoner...]")

    original_run = subprocess.run

    def patched_run(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Заменяет 'Jena' на 'OWLAPI' в аргументах java-команды."""
        if isinstance(cmd, list) and "java" in cmd and "Jena" in cmd:
            cmd[cmd.index("Jena")] = "OWLAPI"
        return original_run(cmd, *args, **kwargs)

    subprocess.run = patched_run  # type: ignore[assignment]
    try:
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
    finally:
        subprocess.run = original_run  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Состояние ПОСЛЕ логического вывода
    # ------------------------------------------------------------------
    print("\n=== ПОСЛЕ ЛОГИЧЕСКОГО ВЫВОДА ===")
    print(f"Доступен ли {module_2.name} для {student.name}? -> {student in module_2.is_available_for}")
    for pr in student.has_progress_record:
        print(f"  Статус {pr.name}: {[s.name for s in pr.has_status]}")
