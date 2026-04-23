"""СВ-5 Subject Subsumption: одни и те же условия, но узкая аудитория.

p_subj_all — grade_required с порогом 70, доступен любому студенту с оценкой.
p_subj_group — AND(grade_required(70), group_restricted(grp_advanced)): те же
условия + узкая группа. Множество студентов, проходящих p_subj_group, —
строгое подмножество проходящих p_subj_all. Subject-subsumption.
"""
from __future__ import annotations

from owlready2 import AllDifferent

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto):
    with onto:
        methodologist = onto.Methodologist("methodologist_smirnov")
        course = onto.Course("course_subject")
        module_one = onto.Module("module_one")
        module_one.is_mandatory = True
        course.has_module = [module_one]
        prereq = onto.Test("quiz_subj_prereq")
        prereq.is_mandatory = True
        guarded = onto.Lecture("elem_s")
        guarded.is_mandatory = True
        module_one.contains_activity = [prereq, guarded]

        grp_advanced = onto.Group("grp_advanced")

        # Широкая политика.
        all_p = onto.AccessPolicy("p_subj_all")
        all_p.rule_type = "grade_required"
        all_p.is_active = True
        all_p.has_author = methodologist
        all_p.targets_element = prereq
        all_p.passing_threshold = 70.0

        # Узкая политика = AND(тот же grade_required) + (group_restricted(advanced)).
        sub_grade = onto.AccessPolicy("p_subj_group_sub_grade")
        sub_grade.rule_type = "grade_required"
        sub_grade.is_active = True
        sub_grade.has_author = methodologist
        sub_grade.targets_element = prereq
        sub_grade.passing_threshold = 70.0

        sub_group = onto.AccessPolicy("p_subj_group_sub_group")
        sub_group.rule_type = "group_restricted"
        sub_group.is_active = True
        sub_group.has_author = methodologist
        sub_group.restricted_to_group = grp_advanced

        narrow = onto.AccessPolicy("p_subj_group")
        narrow.rule_type = "and_combination"
        narrow.is_active = True
        narrow.has_author = methodologist
        narrow.has_subpolicy = [sub_grade, sub_group]
        AllDifferent([sub_grade, sub_group])

        guarded.has_access_policy = [all_p, narrow]

        onto.Student("student_any")
        onto.Student("student_advanced").belongs_to_group = [grp_advanced]


def build_and_save() -> str:
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "bad_sv5_subject.owl")


if __name__ == "__main__":
    print(f"bad_sv5_subject сохранён: {build_and_save()}")
