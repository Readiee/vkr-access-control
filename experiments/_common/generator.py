"""Параметризованный генератор OWL-сценариев для экспериментов

Базовое построение создаёт happy-path ABox заданных размеров;
инжекторы sv* вносят одно нарушение на минимальный фрагмент ABox
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from owlready2 import AllDifferent, World

RANDOM_SEED = 42

# Жёсткое ограничение SWRL-шаблона AND: от двух до трёх подполитик.
# Большая арность ломает двухуровневую семантику satisfies + мета-правило
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

_HERE = Path(__file__).resolve().parent
_TBOX_PATH = _HERE.parents[1] / "code" / "onto" / "ontologies" / "edu_ontology_with_rules.owl"


@dataclass(frozen=True)
class GenerationConfig:
    n_modules: int
    n_activities_per_module: int
    n_students: int
    n_policies: int
    fault: FaultType | None = None
    fault_params: dict[str, Any] = field(default_factory=dict)
    seed: int = RANDOM_SEED
    course_id: str = "course_generated"


def load_tbox(world: World) -> Any:
    onto_uri = f"file://{str(_TBOX_PATH).replace(os.sep, '/')}"
    return world.get_ontology(onto_uri).load()


def build_base_course(world: World, config: GenerationConfig) -> Any:
    onto = load_tbox(world)
    with onto:
        methodologist = onto.Methodologist("methodologist_gen")

        course = onto.Course(config.course_id)
        course.order_index = 0

        modules: list[Any] = []
        activities_by_module: list[list[Any]] = []
        for i in range(config.n_modules):
            m = onto.Module(f"gen_module_{i}")
            m.is_mandatory = True
            m.order_index = i
            acts: list[Any] = []
            for j in range(config.n_activities_per_module):
                a = onto.Lecture(f"gen_activity_{i}_{j}")
                a.is_mandatory = True
                a.order_index = j
                acts.append(a)
            m.contains_activity = acts
            modules.append(m)
            activities_by_module.append(acts)
        course.has_module = modules

        onto.Group("grp_standard_gen")
        for s in range(config.n_students):
            onto.Student(f"gen_student_{s}")

        # Политики: линейная цепочка completion_required между соседними
        # активностями одного модуля; без циклов — базовый случай happy-path
        created = 0
        for mi, acts in enumerate(activities_by_module):
            if created >= config.n_policies:
                break
            for aj in range(1, len(acts)):
                if created >= config.n_policies:
                    break
                guarded = acts[aj]
                prereq = acts[aj - 1]
                p = onto.AccessPolicy(f"gen_p_{mi}_{aj}")
                p.rule_type = "completion_required"
                p.is_active = True
                p.has_author = methodologist
                p.targets_element = prereq
                guarded.has_access_policy = [p]
                created += 1

    return onto


def inject_sv1_disjointness(onto: Any, *, user_id: str) -> None:
    with onto:
        user = onto.Student(user_id)
        user.is_a.append(onto.Methodologist)


def inject_sv2_cycle(onto: Any, *, element_ids: list[str]) -> None:
    if len(element_ids) < 2:
        raise ValueError("inject_sv2_cycle: нужно минимум 2 элемента")
    with onto:
        methodologist = _ensure_methodologist(onto)
        elements = [_lookup_element(onto, eid) for eid in element_ids]
        n = len(elements)
        for i in range(n):
            guarded = elements[i]
            prereq = elements[(i + 1) % n]
            p = onto.AccessPolicy(f"gen_cycle_{i}")
            p.rule_type = "completion_required"
            p.is_active = True
            p.has_author = methodologist
            p.targets_element = prereq
            existing = list(guarded.has_access_policy or [])
            guarded.has_access_policy = existing + [p]


def inject_sv3_atomic_threshold(
    onto: Any,
    *,
    element_id: str,
    bad_threshold: float,
) -> None:
    if 0.0 <= bad_threshold <= 100.0:
        raise ValueError(
            f"inject_sv3_atomic_threshold: threshold={bad_threshold} внутри [0,100], нарушения не будет"
        )
    with onto:
        methodologist = _ensure_methodologist(onto)
        guarded = _lookup_element(onto, element_id)
        prereq = _ensure_prereq_test(onto)
        p = onto.AccessPolicy("gen_unreach_threshold")
        p.rule_type = "grade_required"
        p.is_active = True
        p.has_author = methodologist
        p.targets_element = prereq
        p.passing_threshold = float(bad_threshold)
        existing = list(guarded.has_access_policy or [])
        guarded.has_access_policy = existing + [p]


def inject_sv3_empty_date_window(
    onto: Any,
    *,
    element_id: str,
    valid_from: dt.datetime,
    valid_until: dt.datetime,
) -> None:
    if valid_from <= valid_until:
        raise ValueError("inject_sv3_empty_date_window: valid_from должен быть позже valid_until")
    with onto:
        methodologist = _ensure_methodologist(onto)
        guarded = _lookup_element(onto, element_id)
        p = onto.AccessPolicy("gen_unreach_date")
        p.rule_type = "date_restricted"
        p.is_active = True
        p.has_author = methodologist
        p.valid_from = valid_from
        p.valid_until = valid_until
        existing = list(guarded.has_access_policy or [])
        guarded.has_access_policy = existing + [p]


def inject_sv3_structural(onto: Any, *, element_ids: list[str]) -> None:
    if len(element_ids) < 3:
        raise ValueError("inject_sv3_structural: нужно минимум 3 элемента для замкнутой цепочки")
    inject_sv2_cycle(onto, element_ids=element_ids)


def inject_sv4_redundant(
    onto: Any,
    *,
    element_id: str,
    thresholds: tuple[float, float],
) -> None:
    strong_threshold, weak_threshold = thresholds
    if strong_threshold <= weak_threshold:
        raise ValueError(
            "inject_sv4_redundant: strong threshold должен быть строго выше weak"
        )
    with onto:
        methodologist = _ensure_methodologist(onto)
        guarded = _lookup_element(onto, element_id)
        prereq = _ensure_prereq_test(onto)
        strong = onto.AccessPolicy("gen_red_strong")
        strong.rule_type = "grade_required"
        strong.is_active = True
        strong.has_author = methodologist
        strong.targets_element = prereq
        strong.passing_threshold = float(strong_threshold)

        weak = onto.AccessPolicy("gen_red_weak")
        weak.rule_type = "grade_required"
        weak.is_active = True
        weak.has_author = methodologist
        weak.targets_element = prereq
        weak.passing_threshold = float(weak_threshold)

        existing = list(guarded.has_access_policy or [])
        guarded.has_access_policy = existing + [strong, weak]


def inject_sv5_subject(
    onto: Any,
    *,
    element_id: str,
    group_id: str,
    base_threshold: float,
) -> None:
    with onto:
        methodologist = _ensure_methodologist(onto)
        guarded = _lookup_element(onto, element_id)
        prereq = _ensure_prereq_test(onto)
        group = onto.Group(group_id)

        all_p = onto.AccessPolicy("gen_subj_all")
        all_p.rule_type = "grade_required"
        all_p.is_active = True
        all_p.has_author = methodologist
        all_p.targets_element = prereq
        all_p.passing_threshold = float(base_threshold)

        sub_grade = onto.AccessPolicy("gen_subj_group_sub_grade")
        sub_grade.rule_type = "grade_required"
        sub_grade.is_active = True
        sub_grade.has_author = methodologist
        sub_grade.targets_element = prereq
        sub_grade.passing_threshold = float(base_threshold)

        sub_group = onto.AccessPolicy("gen_subj_group_sub_group")
        sub_group.rule_type = "group_restricted"
        sub_group.is_active = True
        sub_group.has_author = methodologist
        sub_group.restricted_to_group = group

        narrow = onto.AccessPolicy("gen_subj_group")
        narrow.rule_type = "and_combination"
        narrow.is_active = True
        narrow.has_author = methodologist
        narrow.has_subpolicy = [sub_grade, sub_group]
        AllDifferent([sub_grade, sub_group])

        existing = list(guarded.has_access_policy or [])
        guarded.has_access_policy = existing + [all_p, narrow]

        onto.Student("gen_student_advanced").belongs_to_group = [group]


def save_scenario(onto: Any, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onto.save(file=str(output_path), format="rdfxml")
    return output_path


def generate_scenario(config: GenerationConfig, output_path: Path) -> Path:
    import random
    random.seed(config.seed)

    world = World()
    onto = build_base_course(world, config)

    if config.fault is not None:
        _apply_fault(onto, config)

    return save_scenario(onto, output_path)


def _apply_fault(onto: Any, config: GenerationConfig) -> None:
    params = dict(config.fault_params)
    if config.fault == "sv1_disjointness":
        inject_sv1_disjointness(onto, user_id=params.get("user_id", "gen_mixed_role"))
    elif config.fault == "sv2_cycle":
        inject_sv2_cycle(onto, element_ids=params["element_ids"])
    elif config.fault == "sv3_atomic_threshold":
        inject_sv3_atomic_threshold(
            onto,
            element_id=params["element_id"],
            bad_threshold=params.get("bad_threshold", 150.0),
        )
    elif config.fault == "sv3_empty_date":
        inject_sv3_empty_date_window(
            onto,
            element_id=params["element_id"],
            valid_from=params.get("valid_from", dt.datetime(2026, 6, 1)),
            valid_until=params.get("valid_until", dt.datetime(2026, 5, 1)),
        )
    elif config.fault == "sv3_structural":
        inject_sv3_structural(onto, element_ids=params["element_ids"])
    elif config.fault == "sv4_redundant":
        inject_sv4_redundant(
            onto,
            element_id=params["element_id"],
            thresholds=params.get("thresholds", (80.0, 60.0)),
        )
    elif config.fault == "sv5_subject":
        inject_sv5_subject(
            onto,
            element_id=params["element_id"],
            group_id=params.get("group_id", "grp_advanced_gen"),
            base_threshold=params.get("base_threshold", 70.0),
        )
    else:
        raise ValueError(f"Неизвестный fault: {config.fault}")


def _ensure_methodologist(onto: Any) -> Any:
    existing = onto.search_one(type=onto.Methodologist)
    if existing is not None:
        return existing
    return onto.Methodologist("methodologist_gen")


def _ensure_prereq_test(onto: Any) -> Any:
    existing = onto.search_one(iri=f"*gen_prereq_test", type=onto.Test)
    if existing is not None:
        return existing
    with onto:
        prereq = onto.Test("gen_prereq_test")
        prereq.is_mandatory = True
        course = onto.search_one(type=onto.Course)
        modules = list(course.has_module) if course is not None else []
        if modules:
            host = modules[0]
            existing_acts = list(host.contains_activity or [])
            host.contains_activity = existing_acts + [prereq]
    return prereq


def _lookup_element(onto: Any, element_id: str) -> Any:
    for cls_name in ("LearningActivity", "Lecture", "Test", "Practice", "Module", "Course"):
        cls = getattr(onto, cls_name, None)
        if cls is None:
            continue
        found = onto.search_one(iri=f"*{element_id}", type=cls)
        if found is not None:
            return found
    raise KeyError(f"Элемент {element_id!r} не найден в онтологии")
