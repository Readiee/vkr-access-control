"""СВ-1 Consistency: один индивид одновременно Student и Methodologist.

Классы User-субтипы объявлены disjoint в TBox (§1.5). Pellet при reasoning
должен выбросить InconsistentOntologyError. VerificationService ловит это
и возвращает СВ-1 failed.
"""
from __future__ import annotations

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        course = onto.Course("course_minimal")
        module_one = onto.Module("module_m1")
        course.has_module = [module_one]

        user = onto.Student("user_mixed_role")
        user.is_a.append(onto.Methodologist)  # нарушение AllDisjoint(Student, Methodologist)

        onto.Student("student_normal")


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv1_disjointness.owl")


if __name__ == "__main__":
    print(f"bad_sv1 сохранён: {build_and_save()}")
