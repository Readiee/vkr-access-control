"""СВ-2 Acyclicity: два модуля взаимно требуют завершения друг друга.

Split-node DiGraph (А1): completion_required → дуга tgt.complete → src.access.
Цикл в пути module_A.access → module_A.complete → module_B.access → module_B.complete → module_A.access.
"""
from __future__ import annotations

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        methodologist = onto.Methodologist("methodologist_smirnov")
        course = onto.Course("course_cycle")
        module_a = onto.Module("module_A"); module_a.is_required = [True]
        module_b = onto.Module("module_B"); module_b.is_required = [True]
        course.has_module = [module_a, module_b]

        p_ab = onto.AccessPolicy("p_cycle_ab")
        p_ab.rule_type = ["completion_required"]
        p_ab.is_active = [True]
        p_ab.has_author = [methodologist]
        p_ab.targets_element = [module_b]
        module_a.has_access_policy = [p_ab]

        p_ba = onto.AccessPolicy("p_cycle_ba")
        p_ba.rule_type = ["completion_required"]
        p_ba.is_active = [True]
        p_ba.has_author = [methodologist]
        p_ba.targets_element = [module_a]
        module_b.has_access_policy = [p_ba]


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv2_cycle.owl")


if __name__ == "__main__":
    print(f"bad_sv2 сохранён: {build_and_save()}")
