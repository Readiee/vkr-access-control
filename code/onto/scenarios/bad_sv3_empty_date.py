"""СВ-3 Reachability: пустое окно valid_from > valid_until"""
from __future__ import annotations

import datetime

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        methodologist = onto.Methodologist("methodologist_smirnov")
        course = onto.Course("course_empty_window")
        module_one = onto.Module("module_one"); module_one.is_mandatory = True
        course.has_module = [module_one]
        guarded = onto.Lecture("guarded_by_empty_window"); guarded.is_mandatory = True
        module_one.contains_activity = [guarded]

        p = onto.AccessPolicy("p_unreach_date")
        p.rule_type = "date_restricted"
        p.is_active = True
        p.has_author = methodologist
        p.valid_from = datetime.datetime(2026, 6, 1)
        p.valid_until = datetime.datetime(2026, 5, 1)
        guarded.has_access_policy = [p]

        onto.Student("student_any")


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv3_empty_date.owl")


if __name__ == "__main__":
    print(f"bad_sv3_empty_date сохранён: {build_and_save()}")
