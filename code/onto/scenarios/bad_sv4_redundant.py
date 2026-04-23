"""СВ-4 Redundancy: две grade_required на одном элементе, одна поглощает другую.

threshold=80 строго сильнее threshold=60 по одному и тому же prerequisite:
grade≥80 ⟹ grade≥60. В OR-семантике шага 2 достаточно любой политики →
p_red_strong redundant относительно p_red_weak.
"""
from __future__ import annotations

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        methodologist = onto.Methodologist("methodologist_smirnov")
        course = onto.Course("course_redundant")
        module_one = onto.Module("module_one")
        module_one.is_mandatory = True
        course.has_module = [module_one]
        prereq = onto.Test("quiz_r_prereq")
        prereq.is_mandatory = True
        guarded = onto.Test("quiz_r")
        guarded.is_mandatory = True
        module_one.contains_activity = [prereq, guarded]

        strong = onto.AccessPolicy("p_red_strong")
        strong.rule_type = "grade_required"
        strong.is_active = True
        strong.has_author = methodologist
        strong.targets_element = prereq
        strong.passing_threshold = 80.0

        weak = onto.AccessPolicy("p_red_weak")
        weak.rule_type = "grade_required"
        weak.is_active = True
        weak.has_author = methodologist
        weak.targets_element = prereq
        weak.passing_threshold = 60.0

        guarded.has_access_policy = [strong, weak]

        onto.Student("student_any")


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv4_redundant.owl")


if __name__ == "__main__":
    print(f"bad_sv4_redundant сохранён: {build_and_save()}")
