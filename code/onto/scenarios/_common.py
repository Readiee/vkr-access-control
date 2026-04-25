"""Утилиты сценариев: загрузка TBox с SWRL, сохранение отдельного мира"""
from __future__ import annotations

import os
from typing import Tuple

from owlready2 import World

HERE = os.path.dirname(os.path.abspath(__file__))
ONTO_DIR = os.path.abspath(os.path.join(HERE, "..", "ontologies"))
TBOX_PATH = os.path.join(ONTO_DIR, "edu_ontology_with_rules.owl")
SCENARIO_DIR = os.path.join(ONTO_DIR, "scenarios")


def load_tbox_in_isolated_world() -> Tuple[World, object]:
    """Загрузить онтологию с SWRL в изолированный World

    Изолированный мир нужен, когда в одном процессе собираются несколько сценариев
    подряд: default_world накапливает индивидов между прогонами и ломает семантику
    """
    world = World()
    onto = world.get_ontology(f"file://{TBOX_PATH.replace(os.sep, '/')}").load()
    return world, onto


def save_scenario(onto: object, filename: str) -> str:
    """Сохранить сценарий в ontologies/scenarios/<filename>, вернуть абсолютный путь"""
    os.makedirs(SCENARIO_DIR, exist_ok=True)
    path = os.path.join(SCENARIO_DIR, filename)
    onto.save(file=path, format="rdfxml")
    return path
