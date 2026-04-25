"""Заполнение ABox демо-курса

Тонкая обёртка над scenarios/happy_path.py: сценарий happy-path одновременно
используется как основной демонстрационный ABox и как фикстура для
интеграционных тестов. Результат сохраняется в demo_knowledge_base.owl
и в ontologies/scenarios/happy_path.owl
"""
from __future__ import annotations

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS_DIR = os.path.abspath(os.path.join(HERE, "..", "scenarios"))
ONTO_DIR = os.path.abspath(os.path.join(HERE, "..", "ontologies"))

sys.path.insert(0, SCENARIOS_DIR)

from happy_path import build_and_save  # noqa: E402

scenario_path = build_and_save()
legacy_path = os.path.join(ONTO_DIR, "demo_knowledge_base.owl")
shutil.copyfile(scenario_path, legacy_path)

print(f"Happy-path ABox: {scenario_path}")
print(f"Копия как demo_knowledge_base.owl: {legacy_path}")
