"""Диагностический прогон резонера на демо-онтологии

Загружает demo_knowledge_base.owl, прогоняет ReasoningOrchestrator и
печатает доступность module_2_functions для student_ivanov до и после
вывода. Используется при локальной отладке SWRL-шаблонов и enricher-а

Запуск: python smoke_reasoner.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_SRC = os.path.abspath(os.path.join(HERE, "..", "..", "backend", "src"))
ONTO_PATH = os.path.abspath(os.path.join(HERE, "..", "ontologies", "demo_knowledge_base.owl"))
sys.path.insert(0, BACKEND_SRC)

from services.ontology_core import OntologyCore  
from services.reasoning import ReasoningOrchestrator  


def main() -> int:
    core = OntologyCore(ONTO_PATH)
    onto = core.onto

    student = onto.search_one(type=onto.Student, iri="*student_ivanov")
    module_2 = onto.search_one(type=onto.CourseStructure, iri="*module_2_functions")
    if student is None or module_2 is None:
        print("Тестовые данные не найдены — запусти 3_seed_demo_data.py.")
        return 1

    print("До вывода:")
    print(f"  {module_2.name} доступен {student.name}? "
          f"{student in (module_2.is_available_for or [])}")
    for pr in student.has_progress_record or []:
        print(f"  {pr.name}: {[s.name for s in pr.has_status]}")

    result = ReasoningOrchestrator(onto).reason()
    print(f"\nРезонер: {result.status} за {result.duration_sec:.2f}s "
          f"(satisfies={result.satisfies_count}, available={result.available_count})")

    print("\nПосле вывода:")
    print(f"  {module_2.name} доступен {student.name}? "
          f"{student in (module_2.is_available_for or [])}")
    for pr in student.has_progress_record or []:
        print(f"  {pr.name}: {[s.name for s in pr.has_status]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
