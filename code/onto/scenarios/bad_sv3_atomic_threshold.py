"""СВ-3 Reachability: threshold вне диапазона оценок

has_grade ∈ [0, 100]. Политика с threshold=150.0 атомарно невыполнима;
поимкой занимается атомарный проход без Pellet
"""
from __future__ import annotations

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        methodologist = onto.Methodologist("methodologist_smirnov")
        course = onto.Course("course_unreach")
        module_one = onto.Module("module_one"); module_one.is_mandatory = True
        course.has_module = [module_one]
        quiz_prereq = onto.Test("quiz_prereq"); quiz_prereq.is_mandatory = True
        guarded = onto.Lecture("guarded_element"); guarded.is_mandatory = True
        module_one.contains_activity = [quiz_prereq, guarded]

        p = onto.AccessPolicy("p_unreach_threshold")
        p.rule_type = "grade_required"
        p.is_active = True
        p.has_author = methodologist
        p.targets_element = quiz_prereq
        p.passing_threshold = 150.0
        guarded.has_access_policy = [p]

        onto.Student("student_any")


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv3_atomic_threshold.owl")


if __name__ == "__main__":
    print(f"bad_sv3_atomic_threshold сохранён: {build_and_save()}")
