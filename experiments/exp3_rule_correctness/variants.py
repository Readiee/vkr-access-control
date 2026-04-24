"""Вариации ABox для увеличения per-type sample size в Эксперименте 2.

Цель — для каждого из 9 типов правил собрать 5-10 ячеек access matrix с разной
комбинацией параметров и состояний студентов (positive + negative). Базовый
happy_path даёт по одной ячейке на тип; эти варианты добавляют покрытие
пограничных случаев (threshold на границе, частичный прогресс, etc.).

Каждая функция build_* собирает ABox вокруг одного типа правил и возвращает
онтологию + ожидания. Expected задаётся независимо — это вторая точка ground
truth (первая — интерпретатор на самом ABox).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable

from owlready2 import AllDifferent, World

from _common.generator import GenerationConfig, build_base_course, save_scenario


@dataclass(frozen=True)
class VariantCase:
    name: str
    rule_type: str
    builder: Callable[[Any], None]
    course_id: str = "course_variant"


def _methodologist(onto):
    existing = onto.search_one(type=onto.Methodologist)
    return existing if existing is not None else onto.Methodologist("methodologist_v")


def _elem(onto, eid):
    for cls_name in ("LearningActivity", "Lecture", "Test", "Practice", "Module"):
        cls = getattr(onto, cls_name, None)
        if cls is None:
            continue
        found = onto.search_one(iri=f"*{eid}", type=cls)
        if found is not None:
            return found
    raise KeyError(eid)


def _add_prereq_test(onto, tid):
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


def _add_progress(onto, student, element, *, grade=None, status=None, pr_id=None):
    with onto:
        pid = pr_id or f"pr_{student.name}_{element.name}"
        pr = onto.ProgressRecord(pid)
        pr.refers_to_element = element
        if grade is not None:
            pr.has_grade = float(grade)
        if status is not None:
            pr.has_status = status
        existing = list(getattr(student, "has_progress_record", []) or [])
        student.has_progress_record = existing + [pr]


# --- builder-ы по типам ---


def _build_completion_variants(onto):
    """3 студента × 2 политики completion_required на разных targets."""
    with onto:
        m = _methodologist(onto)
        target_a = _add_prereq_test(onto, "var_compl_target_a")
        target_b = _add_prereq_test(onto, "var_compl_target_b")
        guarded_a = _elem(onto, "gen_activity_0_0")
        guarded_b = _elem(onto, "gen_activity_0_1")
        p_a = onto.AccessPolicy("var_p_compl_a")
        p_a.rule_type = "completion_required"
        p_a.is_active = True
        p_a.has_author = m
        p_a.targets_element = target_a
        guarded_a.has_access_policy = [p_a]
        p_b = onto.AccessPolicy("var_p_compl_b")
        p_b.rule_type = "completion_required"
        p_b.is_active = True
        p_b.has_author = m
        p_b.targets_element = target_b
        guarded_b.has_access_policy = [p_b]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        # s1 завершил A → guarded_a доступен, B не трогал → guarded_b не доступен
        _add_progress(onto, s1, target_a, status=onto.status_completed, pr_id="var_pr_s1_ta")
        # s2 завершил оба → оба доступны
        _add_progress(onto, s2, target_a, status=onto.status_completed, pr_id="var_pr_s2_ta")
        _add_progress(onto, s2, target_b, status=onto.status_completed, pr_id="var_pr_s2_tb")


def _build_grade_variants(onto):
    """Разные пороги grade_required, три студента с разными оценками."""
    with onto:
        m = _methodologist(onto)
        target = _add_prereq_test(onto, "var_grade_target")
        guarded_low = _elem(onto, "gen_activity_0_0")
        guarded_high = _elem(onto, "gen_activity_0_1")
        p_low = onto.AccessPolicy("var_p_grade_low")
        p_low.rule_type = "grade_required"
        p_low.is_active = True
        p_low.has_author = m
        p_low.targets_element = target
        p_low.passing_threshold = 50.0
        guarded_low.has_access_policy = [p_low]
        p_high = onto.AccessPolicy("var_p_grade_high")
        p_high.rule_type = "grade_required"
        p_high.is_active = True
        p_high.has_author = m
        p_high.targets_element = target
        p_high.passing_threshold = 90.0
        guarded_high.has_access_policy = [p_high]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s3 = _elem_student(onto, "gen_student_2")
        _add_progress(onto, s1, target, grade=40.0, status=onto.status_failed, pr_id="var_pr_s1_grade")
        _add_progress(onto, s2, target, grade=70.0, status=onto.status_completed, pr_id="var_pr_s2_grade")
        _add_progress(onto, s3, target, grade=95.0, status=onto.status_completed, pr_id="var_pr_s3_grade")


def _build_viewed_variants(onto):
    with onto:
        m = _methodologist(onto)
        target = _add_prereq_test(onto, "var_viewed_target")
        guarded = _elem(onto, "gen_activity_0_0")
        p = onto.AccessPolicy("var_p_viewed")
        p.rule_type = "viewed_required"
        p.is_active = True
        p.has_author = m
        p.targets_element = target
        guarded.has_access_policy = [p]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s3 = _elem_student(onto, "gen_student_2")
        _add_progress(onto, s1, target, status=onto.status_viewed, pr_id="var_pr_s1_v")
        _add_progress(onto, s2, target, status=onto.status_completed, pr_id="var_pr_s2_v")
        # s3 — без прогресса → deny


def _build_competency_variants(onto):
    with onto:
        m = _methodologist(onto)
        comp_root = onto.Competency("var_comp_root")
        comp_child = onto.Competency("var_comp_child")
        comp_child.is_subcompetency_of = [comp_root]
        guarded_root = _elem(onto, "gen_activity_0_0")
        guarded_child = _elem(onto, "gen_activity_0_1")
        p_root = onto.AccessPolicy("var_p_comp_root")
        p_root.rule_type = "competency_required"
        p_root.is_active = True
        p_root.has_author = m
        p_root.targets_competency = [comp_root]
        guarded_root.has_access_policy = [p_root]
        p_child = onto.AccessPolicy("var_p_comp_child")
        p_child.rule_type = "competency_required"
        p_child.is_active = True
        p_child.has_author = m
        p_child.targets_competency = [comp_child]
        guarded_child.has_access_policy = [p_child]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s1.has_competency = [comp_child]  # через H-1 получит и root
        s2.has_competency = []  # ни одной — deny обе


def _build_date_variants(onto):
    with onto:
        m = _methodologist(onto)
        guarded_active = _elem(onto, "gen_activity_0_0")
        guarded_past = _elem(onto, "gen_activity_0_1")
        guarded_future = _elem(onto, "gen_activity_0_2")
        p_active = onto.AccessPolicy("var_p_date_active")
        p_active.rule_type = "date_restricted"
        p_active.is_active = True
        p_active.has_author = m
        p_active.valid_from = dt.datetime(2020, 1, 1)
        p_active.valid_until = dt.datetime(2100, 1, 1)
        guarded_active.has_access_policy = [p_active]
        p_past = onto.AccessPolicy("var_p_date_past")
        p_past.rule_type = "date_restricted"
        p_past.is_active = True
        p_past.has_author = m
        p_past.valid_from = dt.datetime(2000, 1, 1)
        p_past.valid_until = dt.datetime(2001, 1, 1)
        guarded_past.has_access_policy = [p_past]
        p_future = onto.AccessPolicy("var_p_date_future")
        p_future.rule_type = "date_restricted"
        p_future.is_active = True
        p_future.has_author = m
        p_future.valid_from = dt.datetime(2099, 1, 1)
        p_future.valid_until = dt.datetime(2100, 1, 1)
        guarded_future.has_access_policy = [p_future]


def _build_group_variants(onto):
    with onto:
        m = _methodologist(onto)
        g_a = onto.Group("var_grp_A")
        g_b = onto.Group("var_grp_B")
        guarded_a = _elem(onto, "gen_activity_0_0")
        guarded_b = _elem(onto, "gen_activity_0_1")
        p_a = onto.AccessPolicy("var_p_grp_a")
        p_a.rule_type = "group_restricted"
        p_a.is_active = True
        p_a.has_author = m
        p_a.restricted_to_group = g_a
        guarded_a.has_access_policy = [p_a]
        p_b = onto.AccessPolicy("var_p_grp_b")
        p_b.rule_type = "group_restricted"
        p_b.is_active = True
        p_b.has_author = m
        p_b.restricted_to_group = g_b
        guarded_b.has_access_policy = [p_b]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s3 = _elem_student(onto, "gen_student_2")
        s1.belongs_to_group = [g_a]
        s2.belongs_to_group = [g_b]
        # s3 — без группы: deny обе


def _build_aggregate_variants(onto):
    with onto:
        m = _methodologist(onto)
        t1 = _add_prereq_test(onto, "var_agg_t1")
        t2 = _add_prereq_test(onto, "var_agg_t2")
        guarded = _elem(onto, "gen_activity_0_0")
        p = onto.AccessPolicy("var_p_agg")
        p.rule_type = "aggregate_required"
        p.is_active = True
        p.has_author = m
        p.aggregate_function = "AVG"
        p.aggregate_elements = [t1, t2]
        p.passing_threshold = 70.0
        guarded.has_access_policy = [p]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s3 = _elem_student(onto, "gen_student_2")
        # s1: AVG=75 → pass
        _add_progress(onto, s1, t1, grade=80.0, status=onto.status_completed, pr_id="var_agg_s1_t1")
        _add_progress(onto, s1, t2, grade=70.0, status=onto.status_completed, pr_id="var_agg_s1_t2")
        # s2: AVG=55 → deny
        _add_progress(onto, s2, t1, grade=60.0, status=onto.status_completed, pr_id="var_agg_s2_t1")
        _add_progress(onto, s2, t2, grade=50.0, status=onto.status_completed, pr_id="var_agg_s2_t2")
        # s3: нет оценок → deny


def _build_and_variants(onto):
    with onto:
        m = _methodologist(onto)
        target = _add_prereq_test(onto, "var_and_target")
        g = onto.Group("var_and_grp")
        guarded = _elem(onto, "gen_activity_0_0")
        sub_compl = onto.AccessPolicy("var_and_sub_compl")
        sub_compl.rule_type = "completion_required"
        sub_compl.is_active = True
        sub_compl.has_author = m
        sub_compl.targets_element = target
        sub_grp = onto.AccessPolicy("var_and_sub_grp")
        sub_grp.rule_type = "group_restricted"
        sub_grp.is_active = True
        sub_grp.has_author = m
        sub_grp.restricted_to_group = g
        p = onto.AccessPolicy("var_and_p")
        p.rule_type = "and_combination"
        p.is_active = True
        p.has_author = m
        p.has_subpolicy = [sub_compl, sub_grp]
        AllDifferent([sub_compl, sub_grp])
        guarded.has_access_policy = [p]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s3 = _elem_student(onto, "gen_student_2")
        s1.belongs_to_group = [g]
        _add_progress(onto, s1, target, status=onto.status_completed, pr_id="var_and_s1")
        # s1: группа + completion → pass
        s2.belongs_to_group = [g]
        # s2: группа, без completion → deny
        _add_progress(onto, s3, target, status=onto.status_completed, pr_id="var_and_s3")
        # s3: completion, без группы → deny


def _build_or_variants(onto):
    with onto:
        m = _methodologist(onto)
        target = _add_prereq_test(onto, "var_or_target")
        g = onto.Group("var_or_grp")
        guarded = _elem(onto, "gen_activity_0_0")
        sub_compl = onto.AccessPolicy("var_or_sub_compl")
        sub_compl.rule_type = "completion_required"
        sub_compl.is_active = True
        sub_compl.has_author = m
        sub_compl.targets_element = target
        sub_grp = onto.AccessPolicy("var_or_sub_grp")
        sub_grp.rule_type = "group_restricted"
        sub_grp.is_active = True
        sub_grp.has_author = m
        sub_grp.restricted_to_group = g
        p = onto.AccessPolicy("var_or_p")
        p.rule_type = "or_combination"
        p.is_active = True
        p.has_author = m
        p.has_subpolicy = [sub_compl, sub_grp]
        guarded.has_access_policy = [p]

        s1 = _elem_student(onto, "gen_student_0")
        s2 = _elem_student(onto, "gen_student_1")
        s3 = _elem_student(onto, "gen_student_2")
        # s1: только группа → pass
        s1.belongs_to_group = [g]
        # s2: только completion → pass
        _add_progress(onto, s2, target, status=onto.status_completed, pr_id="var_or_s2")
        # s3: ничего → deny


def build_variants() -> list[VariantCase]:
    return [
        VariantCase("var_completion", "completion_required", _build_completion_variants),
        VariantCase("var_grade", "grade_required", _build_grade_variants),
        VariantCase("var_viewed", "viewed_required", _build_viewed_variants),
        VariantCase("var_competency", "competency_required", _build_competency_variants),
        VariantCase("var_date", "date_restricted", _build_date_variants),
        VariantCase("var_group", "group_restricted", _build_group_variants),
        VariantCase("var_aggregate", "aggregate_required", _build_aggregate_variants),
        VariantCase("var_and", "and_combination", _build_and_variants),
        VariantCase("var_or", "or_combination", _build_or_variants),
    ]


def _elem_student(onto: Any, sid: str) -> Any:
    found = onto.search_one(iri=f"*{sid}", type=onto.Student)
    if found is not None:
        return found
    return onto.Student(sid)


def materialize_variant(case: VariantCase, output_path: Any) -> Any:
    """Построить happy-path + variant-инъекцию и сохранить в OWL."""
    world = World()
    cfg = GenerationConfig(
        n_modules=2,
        n_activities_per_module=4,
        n_students=3,
        n_policies=0,
        course_id=case.course_id,
    )
    onto = build_base_course(world, cfg)
    case.builder(onto)
    save_scenario(onto, output_path)
    return onto
