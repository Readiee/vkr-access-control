"""СВ-3 Reachability, Проход 2: структурная недостижимость через 3-цикл.

Элементы A, B, C — каждый требует completion следующего. Цикл длиной 3
ловится split-node DiGraph (СВ-2) и подтверждается fixed-point (А4 Проход 2):
ни один студент без прогресса не может войти в замкнутую цепочку.
"""
from __future__ import annotations

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        methodologist = onto.Methodologist("methodologist_smirnov")
        course = onto.Course("course_triangle")
        module_one = onto.Module("module_one")
        module_one.is_mandatory = True
        course.has_module = [module_one]
        a = onto.Lecture("elem_a")
        a.is_mandatory = True
        b = onto.Lecture("elem_b")
        b.is_mandatory = True
        c = onto.Lecture("elem_c")
        c.is_mandatory = True
        module_one.contains_activity = [a, b, c]

        def guard(guarded, prereq, pid):
            p = onto.AccessPolicy(pid)
            p.rule_type = "completion_required"
            p.is_active = True
            p.has_author = methodologist
            p.targets_element = prereq
            guarded.has_access_policy = [p]

        guard(a, b, "p_triangle_a_needs_b")
        guard(b, c, "p_triangle_b_needs_c")
        guard(c, a, "p_triangle_c_needs_a")

        onto.Student("student_any")


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv3_structural.owl")


if __name__ == "__main__":
    print(f"bad_sv3_structural сохранён: {build_and_save()}")
