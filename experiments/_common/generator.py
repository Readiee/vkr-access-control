"""Параметризованный генератор OWL-сценариев для EXP1–EXP5.

Базовое построение создаёт happy-path ABox заданных размеров;
инжекторы sv* вносят одно нарушение на минимальный фрагмент ABox.
Скелет API — тела функций наполняются при расширении выборки в EXP1 full.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from owlready2 import Ontology, World

RANDOM_SEED = 42

# Жёсткое ограничение SWRL-шаблона AND: от двух до трёх подполитик.
# Больше расширит комбинаторный взрыв SWRL и ломает корректность DifferentFrom.
MAX_AND_SUBPOLICIES = 3

FaultType = Literal[
    "sv1_disjointness",
    "sv2_cycle",
    "sv3_atomic_threshold",
    "sv3_empty_date",
    "sv3_structural",
    "sv4_redundant",
    "sv5_subject",
]


@dataclass(frozen=True)
class GenerationConfig:
    n_modules: int
    n_activities_per_module: int
    n_students: int
    n_policies: int
    fault: FaultType | None = None
    seed: int = RANDOM_SEED


def build_base_course(world: World, config: GenerationConfig) -> Ontology:
    raise NotImplementedError("build_base_course")


def inject_sv1_disjointness(onto: Ontology, *, user_id: str) -> None:
    raise NotImplementedError("inject_sv1_disjointness")


def inject_sv2_cycle(onto: Ontology, *, element_ids: list[str]) -> None:
    raise NotImplementedError("inject_sv2_cycle")


def inject_sv3_atomic_threshold(
    onto: Ontology,
    *,
    element_id: str,
    bad_threshold: float,
) -> None:
    raise NotImplementedError("inject_sv3_atomic_threshold")


def inject_sv3_empty_date_window(
    onto: Ontology,
    *,
    element_id: str,
    valid_from: str,
    valid_until: str,
) -> None:
    raise NotImplementedError("inject_sv3_empty_date_window")


def inject_sv3_structural(onto: Ontology, *, element_ids: list[str]) -> None:
    raise NotImplementedError("inject_sv3_structural")


def inject_sv4_redundant(
    onto: Ontology,
    *,
    element_id: str,
    thresholds: tuple[float, float],
) -> None:
    raise NotImplementedError("inject_sv4_redundant")


def inject_sv5_subject(
    onto: Ontology,
    *,
    element_id: str,
    group_id: str,
    base_threshold: float,
) -> None:
    raise NotImplementedError("inject_sv5_subject")


def save_scenario(onto: Ontology, output_path: Path) -> Path:
    raise NotImplementedError("save_scenario")


def generate_scenario(config: GenerationConfig, output_path: Path) -> Path:
    raise NotImplementedError("generate_scenario")
