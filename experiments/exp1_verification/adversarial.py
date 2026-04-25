"""Adversarial boundary-кейсы для EXP1: «почти-нарушения», которые детектор
обязан НЕ помечать как дефект

False positive на любом из них — реальный баг валидатора, не регрессия.

Четыре группы:
  A. Атомарные boundary (threshold=0/100, dates с минимальным валидным окном)
  B. Структурные near-cycle (линейные цепочки, ромб, смесь viewed+completion)
  C. Non-redundancy (одинаковые пороги на разных target'ах, разные типы)
  D. Non-subsumption (непересекающиеся условия, несовместимые группы)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable

from owlready2 import World

from _common.generator import GenerationConfig, build_base_course, save_scenario


@dataclass(frozen=True)
class AdversarialCase:
    name: str
    builder: Callable[[Any], None]
    expected: dict[str, Any]
    include_subsumption: bool = False
    course_id: str = "course_adversarial"
    n_modules: int = 2
    n_activities_per_module: int = 4
    extras: dict[str, Any] = field(default_factory=dict)


def _methodologist(onto):
    existing = onto.search_one(type=onto.Methodologist)
    return existing if existing is not None else onto.Methodologist("methodologist_adv")


def _elem(onto, eid):
    for cls_name in ("LearningActivity", "Lecture", "Test", "Practice", "Module"):
        cls = getattr(onto, cls_name, None)
        if cls is None:
            continue
        found = onto.search_one(iri=f"*{eid}", type=cls)
        if found is not None:
            return found
    raise KeyError(eid)


def _extra_test(onto, tid):
    existing = onto.search_one(iri=f"*{tid}", type=onto.Test)
    if existing is not None:
        return existing
    with onto:
        t = onto.Test(tid)
        t.is_mandatory = True
        course = onto.search_one(type=onto.Course)
        modules = list(course.has_module) if course is not None else []
        if modules:
            host = modules[0]
            host.contains_activity = list(host.contains_activity or []) + [t]
    return t


def _build_thr_zero(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_prereq")
        p = onto.AccessPolicy("adv_p_thr_zero")
        p.rule_type = "grade_required"
        p.is_active = True
        p.has_author = m
        p.targets_element = prereq
        p.passing_threshold = 0.0
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_thr_hundred(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_prereq")
        p = onto.AccessPolicy("adv_p_thr_hundred")
        p.rule_type = "grade_required"
        p.is_active = True
        p.has_author = m
        p.targets_element = prereq
        p.passing_threshold = 100.0
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_date_single_second(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        p = onto.AccessPolicy("adv_p_date_1s")
        p.rule_type = "date_restricted"
        p.is_active = True
        p.has_author = m
        p.valid_from = dt.datetime(2026, 6, 1, 12, 0, 0)
        p.valid_until = dt.datetime(2026, 6, 1, 12, 0, 1)
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_date_same_point(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        p = onto.AccessPolicy("adv_p_date_point")
        p.rule_type = "date_restricted"
        p.is_active = True
        p.has_author = m
        point = dt.datetime(2026, 6, 1, 12, 0, 0)
        p.valid_from = point
        p.valid_until = point
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_aggregate_single(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_agg_elem")
        p = onto.AccessPolicy("adv_p_agg_single")
        p.rule_type = "aggregate_required"
        p.is_active = True
        p.has_author = m
        p.aggregate_function = "AVG"
        p.aggregate_elements = [prereq]
        p.passing_threshold = 50.0
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_linear_chain(onto, length: int):
    with onto:
        m = _methodologist(onto)
        for i in range(1, length):
            guarded = _elem(onto, f"gen_activity_0_{i}")
            prereq = _elem(onto, f"gen_activity_0_{i - 1}")
            p = onto.AccessPolicy(f"adv_p_chain_{i}")
            p.rule_type = "completion_required"
            p.is_active = True
            p.has_author = m
            p.targets_element = prereq
            guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_diamond(onto):
    with onto:
        m = _methodologist(onto)
        a = _elem(onto, "gen_activity_0_0")
        b = _elem(onto, "gen_activity_0_1")
        c = _elem(onto, "gen_activity_0_2")
        d = _elem(onto, "gen_activity_0_3")
        # B и C зависят от A; D зависит от B и C — ацикличный DAG-ромб
        for guarded, prereq, pid in [
            (b, a, "adv_p_diamond_ba"),
            (c, a, "adv_p_diamond_ca"),
        ]:
            p = onto.AccessPolicy(pid)
            p.rule_type = "completion_required"
            p.is_active = True
            p.has_author = m
            p.targets_element = prereq
            guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]
        p_bd = onto.AccessPolicy("adv_p_diamond_db")
        p_bd.rule_type = "completion_required"
        p_bd.is_active = True
        p_bd.has_author = m
        p_bd.targets_element = b
        p_cd = onto.AccessPolicy("adv_p_diamond_dc")
        p_cd.rule_type = "completion_required"
        p_cd.is_active = True
        p_cd.has_author = m
        p_cd.targets_element = c
        d.has_access_policy = list(d.has_access_policy or []) + [p_bd, p_cd]


def _build_red_different_targets(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq_x = _extra_test(onto, "adv_red_prereq_x")
        prereq_y = _extra_test(onto, "adv_red_prereq_y")
        p_x = onto.AccessPolicy("adv_p_red_x")
        p_x.rule_type = "grade_required"
        p_x.is_active = True
        p_x.has_author = m
        p_x.targets_element = prereq_x
        p_x.passing_threshold = 80.0
        p_y = onto.AccessPolicy("adv_p_red_y")
        p_y.rule_type = "grade_required"
        p_y.is_active = True
        p_y.has_author = m
        p_y.targets_element = prereq_y
        p_y.passing_threshold = 80.0
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p_x, p_y]


def _build_red_different_types(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_red_prereq_common")
        p_grade = onto.AccessPolicy("adv_p_red_grade")
        p_grade.rule_type = "grade_required"
        p_grade.is_active = True
        p_grade.has_author = m
        p_grade.targets_element = prereq
        p_grade.passing_threshold = 80.0
        p_viewed = onto.AccessPolicy("adv_p_red_viewed")
        p_viewed.rule_type = "viewed_required"
        p_viewed.is_active = True
        p_viewed.has_author = m
        p_viewed.targets_element = prereq
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p_grade, p_viewed]


def _build_red_single_policy(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_red_solo_prereq")
        p = onto.AccessPolicy("adv_p_red_solo")
        p.rule_type = "grade_required"
        p.is_active = True
        p.has_author = m
        p.targets_element = prereq
        p.passing_threshold = 70.0
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p]


def _build_red_different_guarded(onto):
    with onto:
        m = _methodologist(onto)
        guarded_x = _elem(onto, "gen_activity_0_0")
        guarded_y = _elem(onto, "gen_activity_0_1")
        prereq = _extra_test(onto, "adv_red_split_prereq")
        p1 = onto.AccessPolicy("adv_p_red_split_a")
        p1.rule_type = "grade_required"
        p1.is_active = True
        p1.has_author = m
        p1.targets_element = prereq
        p1.passing_threshold = 80.0
        p2 = onto.AccessPolicy("adv_p_red_split_b")
        p2.rule_type = "grade_required"
        p2.is_active = True
        p2.has_author = m
        p2.targets_element = prereq
        p2.passing_threshold = 60.0
        guarded_x.has_access_policy = list(guarded_x.has_access_policy or []) + [p1]
        guarded_y.has_access_policy = list(guarded_y.has_access_policy or []) + [p2]


def _build_red_different_groups(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        g1 = onto.Group("adv_grp_g1")
        g2 = onto.Group("adv_grp_g2")
        p1 = onto.AccessPolicy("adv_p_red_grp_g1")
        p1.rule_type = "group_restricted"
        p1.is_active = True
        p1.has_author = m
        p1.restricted_to_group = g1
        p2 = onto.AccessPolicy("adv_p_red_grp_g2")
        p2.rule_type = "group_restricted"
        p2.is_active = True
        p2.has_author = m
        p2.restricted_to_group = g2
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p1, p2]


def _build_sub_different_thresholds(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_sub_diff_thr_prereq")
        g = onto.Group("adv_grp_sub_diff_thr")
        p_all = onto.AccessPolicy("adv_p_sub_diff_all")
        p_all.rule_type = "grade_required"
        p_all.is_active = True
        p_all.has_author = m
        p_all.targets_element = prereq
        p_all.passing_threshold = 70.0
        p_group = onto.AccessPolicy("adv_p_sub_diff_group")
        p_group.rule_type = "group_restricted"
        p_group.is_active = True
        p_group.has_author = m
        p_group.restricted_to_group = g
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p_all, p_group]


def _build_sub_different_targets(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq_x = _extra_test(onto, "adv_sub_target_x")
        prereq_y = _extra_test(onto, "adv_sub_target_y")
        p_x = onto.AccessPolicy("adv_p_sub_tx")
        p_x.rule_type = "grade_required"
        p_x.is_active = True
        p_x.has_author = m
        p_x.targets_element = prereq_x
        p_x.passing_threshold = 70.0
        p_y = onto.AccessPolicy("adv_p_sub_ty")
        p_y.rule_type = "grade_required"
        p_y.is_active = True
        p_y.has_author = m
        p_y.targets_element = prereq_y
        p_y.passing_threshold = 70.0
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p_x, p_y]


def _build_sub_unrelated_groups(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        g_a = onto.Group("adv_grp_A")
        g_b = onto.Group("adv_grp_B")
        p_a = onto.AccessPolicy("adv_p_sub_grp_A")
        p_a.rule_type = "group_restricted"
        p_a.is_active = True
        p_a.has_author = m
        p_a.restricted_to_group = g_a
        p_b = onto.AccessPolicy("adv_p_sub_grp_B")
        p_b.rule_type = "group_restricted"
        p_b.is_active = True
        p_b.has_author = m
        p_b.restricted_to_group = g_b
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p_a, p_b]


def _build_sub_types_dont_subsume(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        prereq = _extra_test(onto, "adv_sub_mixed_prereq")
        p_grade = onto.AccessPolicy("adv_p_sub_grade")
        p_grade.rule_type = "grade_required"
        p_grade.is_active = True
        p_grade.has_author = m
        p_grade.targets_element = prereq
        p_grade.passing_threshold = 70.0
        p_date = onto.AccessPolicy("adv_p_sub_date")
        p_date.rule_type = "date_restricted"
        p_date.is_active = True
        p_date.has_author = m
        p_date.valid_from = dt.datetime(2026, 1, 1)
        p_date.valid_until = dt.datetime(2026, 12, 31)
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p_grade, p_date]


def _build_sub_distinct_competencies(onto):
    with onto:
        m = _methodologist(onto)
        guarded = _elem(onto, "gen_activity_0_0")
        c1 = onto.Competency("adv_comp_math")
        c2 = onto.Competency("adv_comp_history")
        # Оценивающие элементы для каждой компетенции: без них никто не может
        # получить компетенцию и reachability корректно падает в failed
        assessor_math = _elem(onto, "gen_activity_0_2")
        assessor_history = _elem(onto, "gen_activity_0_3")
        assessor_math.assesses = [c1]
        assessor_history.assesses = [c2]
        p1 = onto.AccessPolicy("adv_p_sub_comp_math")
        p1.rule_type = "competency_required"
        p1.is_active = True
        p1.has_author = m
        p1.targets_competency = [c1]
        p2 = onto.AccessPolicy("adv_p_sub_comp_history")
        p2.rule_type = "competency_required"
        p2.is_active = True
        p2.has_author = m
        p2.targets_competency = [c2]
        guarded.has_access_policy = list(guarded.has_access_policy or []) + [p1, p2]


def build_adversarial_cases() -> list[AdversarialCase]:
    happy_baseline = {"consistency": "passed", "acyclicity": "passed", "reachability": "passed"}
    full_happy = {**happy_baseline, "redundancy": "passed", "subsumption": "passed"}
    return [
        AdversarialCase("adv_thr_zero",              _build_thr_zero,                happy_baseline),
        AdversarialCase("adv_thr_hundred",           _build_thr_hundred,             happy_baseline),
        AdversarialCase("adv_date_single_second",    _build_date_single_second,      happy_baseline),
        AdversarialCase("adv_date_same_point",       _build_date_same_point,         happy_baseline),
        AdversarialCase("adv_aggregate_single_elem", _build_aggregate_single,        happy_baseline),
        AdversarialCase("adv_chain_linear_3",        lambda o: _build_linear_chain(o, 3), happy_baseline, n_activities_per_module=3),
        AdversarialCase("adv_chain_linear_5",        lambda o: _build_linear_chain(o, 5), happy_baseline, n_activities_per_module=5),
        AdversarialCase("adv_chain_linear_8",        lambda o: _build_linear_chain(o, 8), happy_baseline, n_activities_per_module=8),
        AdversarialCase("adv_diamond",               _build_diamond,                  happy_baseline, n_activities_per_module=4),
        AdversarialCase("adv_red_diff_targets",      _build_red_different_targets,    full_happy, include_subsumption=True),
        AdversarialCase("adv_red_diff_types",        _build_red_different_types,      full_happy, include_subsumption=True),
        AdversarialCase("adv_red_single_policy",     _build_red_single_policy,        full_happy, include_subsumption=True),
        AdversarialCase("adv_red_diff_guarded",      _build_red_different_guarded,    full_happy, include_subsumption=True),
        AdversarialCase("adv_red_diff_groups",       _build_red_different_groups,     full_happy, include_subsumption=True),
        AdversarialCase("adv_sub_diff_thresholds",   _build_sub_different_thresholds, full_happy, include_subsumption=True),
        AdversarialCase("adv_sub_diff_targets",      _build_sub_different_targets,    full_happy, include_subsumption=True),
        AdversarialCase("adv_sub_unrelated_groups",  _build_sub_unrelated_groups,     full_happy, include_subsumption=True),
        AdversarialCase("adv_sub_types_dont_subsume", _build_sub_types_dont_subsume,  full_happy, include_subsumption=True),
        AdversarialCase("adv_sub_distinct_comps",    _build_sub_distinct_competencies, full_happy, include_subsumption=True, n_activities_per_module=4),
    ]


def build_scenario(case: AdversarialCase, output_path: Any) -> Any:
    world = World()
    config = GenerationConfig(
        n_modules=case.n_modules,
        n_activities_per_module=case.n_activities_per_module,
        n_students=2,
        n_policies=0,
        course_id=case.course_id,
    )
    onto = build_base_course(world, config)
    case.builder(onto)
    save_scenario(onto, output_path)
    return onto
