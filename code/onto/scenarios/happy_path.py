"""Happy-path демо-курс Python (SAT_DATA_MODELS §6.3–6.7).

Полный ABox: 4 студента, 3 группы, 4 компетенции с иерархией, 9 политик всех
типов, 4 модуля + 3 дополнительных элемента, 11 записей прогресса. После запуска
резонера выводятся satisfies + is_available_for строго по таблице §6.7.

Запуск как скрипт: перезаписывает ontologies/scenarios/happy_path.owl.
Как модуль: build(onto) наполняет переданную онтологию, для тестов.
"""
from __future__ import annotations

import datetime
from typing import Any

from owlready2 import AllDifferent

from _common import load_tbox_in_isolated_world, save_scenario


def build(onto: Any) -> None:
    """Наполнить онтологию индивидами happy-path."""
    with onto:
        # --- Группы ---
        grp_standard = onto.Group("grp_standard"); grp_standard.label = ["Стандартный поток"]
        grp_advanced = onto.Group("grp_advanced"); grp_advanced.label = ["Продвинутый поток"]
        grp_remote = onto.Group("grp_remote"); grp_remote.label = ["Дистанционный поток"]

        # --- Компетенции + иерархия ---
        comp_python = onto.Competency("comp_python"); comp_python.label = ["Python (общая)"]
        comp_basic_syntax = onto.Competency("comp_basic_syntax"); comp_basic_syntax.label = ["Базовый синтаксис"]
        comp_functions = onto.Competency("comp_functions"); comp_functions.label = ["Функции"]
        comp_oop = onto.Competency("comp_oop"); comp_oop.label = ["ООП"]
        comp_basic_syntax.is_subcompetency_of = [comp_python]
        comp_functions.is_subcompetency_of = [comp_python]
        comp_oop.is_subcompetency_of = [comp_functions]

        # --- Методист + студенты ---
        methodologist_smirnov = onto.Methodologist("methodologist_smirnov")
        methodologist_smirnov.label = ["Смирнов О. В. (методист)"]

        student_ivanov = onto.Student("student_ivanov"); student_ivanov.label = ["Иванов И. И."]
        student_petrov = onto.Student("student_petrov"); student_petrov.label = ["Петров П. П."]
        student_sidorov = onto.Student("student_sidorov"); student_sidorov.label = ["Сидоров С. С."]
        student_korolev = onto.Student("student_korolev"); student_korolev.label = ["Королёв К. К."]

        student_ivanov.belongs_to_group = [grp_standard]
        student_petrov.belongs_to_group = [grp_standard]
        student_sidorov.belongs_to_group = [grp_advanced]
        student_korolev.belongs_to_group = [grp_remote]

        student_ivanov.has_competency = [comp_basic_syntax]
        student_sidorov.has_competency = [comp_basic_syntax, comp_functions, comp_oop]
        student_korolev.has_competency = [comp_basic_syntax]

        # --- Структура курса ---
        course = onto.Course("course_python_basics"); course.label = ["Основы Python"]
        course.order_index = [0]

        m0 = onto.Module("module_0_intro"); m0.label = ["Модуль 0. Введение"]
        m0.is_required = [False]; m0.order_index = [0]
        m1 = onto.Module("module_1_syntax"); m1.label = ["Модуль 1. Синтаксис"]
        m1.is_required = [True]; m1.order_index = [1]
        m2 = onto.Module("module_2_functions"); m2.label = ["Модуль 2. Функции"]
        m2.is_required = [True]; m2.order_index = [2]
        m3 = onto.Module("module_3_oop"); m3.label = ["Модуль 3. ООП"]
        m3.is_required = [True]; m3.order_index = [3]
        course.has_module = [m0, m1, m2, m3]

        lec0 = onto.Lecture("lecture_0_welcome"); lec0.label = ["Приветственная лекция"]
        lec0.is_required = [True]; lec0.order_index = [0]
        m0.contains_element = [lec0]

        lec1 = onto.Lecture("lecture_1_variables"); lec1.label = ["Лекция. Переменные и типы"]
        lec1.is_required = [True]; lec1.order_index = [0]
        lec2 = onto.Lecture("lecture_2_operators"); lec2.label = ["Лекция. Операторы"]
        lec2.is_required = [True]; lec2.order_index = [1]
        quiz1 = onto.Test("quiz_1"); quiz1.label = ["Квиз. Синтаксис"]
        quiz1.is_required = [True]; quiz1.order_index = [2]
        quiz1.assesses = [comp_basic_syntax]
        prac1 = onto.Practice("practice_1"); prac1.label = ["Практика. Синтаксис"]
        prac1.is_required = [True]; prac1.order_index = [3]
        prac1.assesses = [comp_basic_syntax]
        m1.contains_element = [lec1, lec2, quiz1, prac1]

        lec3 = onto.Lecture("lecture_3_functions"); lec3.label = ["Лекция. Функции"]
        lec3.is_required = [True]; lec3.order_index = [0]
        quiz2 = onto.Test("quiz_2"); quiz2.label = ["Квиз. Функции"]
        quiz2.is_required = [True]; quiz2.order_index = [1]
        quiz2.assesses = [comp_functions]
        prac2 = onto.Practice("practice_2"); prac2.label = ["Практика. Функции"]
        prac2.is_required = [True]; prac2.order_index = [2]
        prac2.assesses = [comp_functions]
        m2.contains_element = [lec3, quiz2, prac2]

        lec4 = onto.Lecture("lecture_4_classes"); lec4.label = ["Лекция. Классы"]
        lec4.is_required = [True]; lec4.order_index = [0]
        quiz3 = onto.Test("quiz_3"); quiz3.label = ["Квиз. ООП"]
        quiz3.is_required = [True]; quiz3.order_index = [1]
        prac3 = onto.Practice("practice_3"); prac3.label = ["Практика. ООП"]
        prac3.is_required = [True]; prac3.order_index = [2]
        # comp_oop получают через перезачёт (has_competency напрямую) или через
        # наследование H-1 с внешних курсов. Attaching assesses на элементы внутри
        # module_3_oop (защищённого comp_functions) дал бы структурный цикл через
        # competency-раскрытие + hierarchy descent — GraphValidator детектирует.
        m3.contains_element = [lec4, quiz3, prac3]

        # Дополнительная секция курса: contains_element в TBox требует domain=Module,
        # поэтому прямые элементы курса оборачиваем в module_extras.
        m_extras = onto.Module("module_extras"); m_extras.label = ["Дополнительно"]
        m_extras.is_required = [False]; m_extras.order_index = [4]
        course.has_module = list(course.has_module) + [m_extras]

        workshop = onto.Lecture("seasonal_workshop"); workshop.label = ["Семинар (ограничен по времени)"]
        workshop.is_required = [False]; workshop.order_index = [0]
        extra = onto.Lecture("extra_material"); extra.label = ["Материал для продвинутого потока"]
        extra.is_required = [False]; extra.order_index = [1]
        final_exam = onto.Test("final_exam"); final_exam.label = ["Итоговый экзамен"]
        final_exam.is_required = [True]; final_exam.order_index = [2]
        m_extras.contains_element = [workshop, extra, final_exam]

        # --- Политики (9 типов) ---
        p1 = onto.AccessPolicy("p1_lecture2_requires_lecture1")
        p1.rule_type = ["completion_required"]
        p1.is_active = [True]
        p1.has_author = [methodologist_smirnov]
        p1.targets_element = [lec1]
        lec2.has_access_policy = [p1]

        p2 = onto.AccessPolicy("p2_module2_requires_quiz1_grade")
        p2.rule_type = ["grade_required"]
        p2.is_active = [True]
        p2.has_author = [methodologist_smirnov]
        p2.targets_element = [quiz1]
        p2.passing_threshold = [75.0]
        m2.has_access_policy = [p2]

        p3 = onto.AccessPolicy("p3_quiz1_requires_viewed_lecture1")
        p3.rule_type = ["viewed_required"]
        p3.is_active = [True]
        p3.has_author = [methodologist_smirnov]
        p3.targets_element = [lec1]
        quiz1.has_access_policy = [p3]

        p4 = onto.AccessPolicy("p4_module3_requires_comp_functions")
        p4.rule_type = ["competency_required"]
        p4.is_active = [True]
        p4.has_author = [methodologist_smirnov]
        p4.targets_competency = [comp_functions]
        m3.has_access_policy = [p4]

        p5 = onto.AccessPolicy("p5_seasonal_workshop_date_window")
        p5.rule_type = ["date_restricted"]
        p5.is_active = [True]
        p5.has_author = [methodologist_smirnov]
        p5.valid_from = [datetime.datetime(2026, 4, 15, 0, 0, 0)]
        p5.valid_until = [datetime.datetime(2026, 6, 30, 23, 59, 59)]
        workshop.has_access_policy = [p5]

        # AND: lecture_4_classes completion + quiz_3 grade>=70
        p6_sub_a = onto.AccessPolicy("p6_sub_a_lecture4_completion")
        p6_sub_a.rule_type = ["completion_required"]
        p6_sub_a.is_active = [True]
        p6_sub_a.has_author = [methodologist_smirnov]
        p6_sub_a.targets_element = [lec4]

        p6_sub_b = onto.AccessPolicy("p6_sub_b_quiz3_grade70")
        p6_sub_b.rule_type = ["grade_required"]
        p6_sub_b.is_active = [True]
        p6_sub_b.has_author = [methodologist_smirnov]
        p6_sub_b.targets_element = [quiz3]
        p6_sub_b.passing_threshold = [70.0]

        p6 = onto.AccessPolicy("p6_practice3_and")
        p6.rule_type = ["and_combination"]
        p6.is_active = [True]
        p6.has_author = [methodologist_smirnov]
        p6.has_subpolicy = [p6_sub_a, p6_sub_b]
        AllDifferent([p6_sub_a, p6_sub_b])
        prac3.has_access_policy = [p6]

        # OR: comp_basic_syntax OR quiz_2 grade>=85
        p7_sub_a = onto.AccessPolicy("p7_sub_a_comp_basic_syntax")
        p7_sub_a.rule_type = ["competency_required"]
        p7_sub_a.is_active = [True]
        p7_sub_a.has_author = [methodologist_smirnov]
        p7_sub_a.targets_competency = [comp_basic_syntax]

        p7_sub_b = onto.AccessPolicy("p7_sub_b_quiz2_grade85")
        p7_sub_b.rule_type = ["grade_required"]
        p7_sub_b.is_active = [True]
        p7_sub_b.has_author = [methodologist_smirnov]
        p7_sub_b.targets_element = [quiz2]
        p7_sub_b.passing_threshold = [85.0]

        p7 = onto.AccessPolicy("p7_quiz3_or")
        p7.rule_type = ["or_combination"]
        p7.is_active = [True]
        p7.has_author = [methodologist_smirnov]
        p7.has_subpolicy = [p7_sub_a, p7_sub_b]
        quiz3.has_access_policy = [p7]

        p8 = onto.AccessPolicy("p8_extra_material_advanced")
        p8.rule_type = ["group_restricted"]
        p8.is_active = [True]
        p8.has_author = [methodologist_smirnov]
        p8.restricted_to_group = [grp_advanced]
        extra.has_access_policy = [p8]

        p9 = onto.AccessPolicy("p9_final_exam_avg_prereq")
        p9.rule_type = ["aggregate_required"]
        p9.is_active = [True]
        p9.has_author = [methodologist_smirnov]
        p9.aggregate_function = "AVG"
        p9.aggregate_elements = [quiz1, quiz2, prac1, prac2]
        p9.passing_threshold = [70.0]
        final_exam.has_access_policy = [p9]

        # --- Прогресс (таблица §6.6) ---
        _progress(onto, "pr_ivanov_l0_viewed", student_ivanov, lec0, status=onto.status_viewed)
        _progress(onto, "pr_petrov_l0_viewed", student_petrov, lec0, status=onto.status_viewed)
        _progress(onto, "pr_sidorov_l0_viewed", student_sidorov, lec0, status=onto.status_viewed)

        _progress(onto, "pr_ivanov_l1_completed", student_ivanov, lec1, status=onto.status_completed)
        _progress(onto, "pr_petrov_l1_viewed", student_petrov, lec1, status=onto.status_viewed)
        _progress(onto, "pr_sidorov_l1_completed", student_sidorov, lec1, status=onto.status_completed)

        _progress(onto, "pr_ivanov_l2_completed", student_ivanov, lec2, status=onto.status_completed)
        _progress(onto, "pr_sidorov_l2_completed", student_sidorov, lec2, status=onto.status_completed)

        _progress(onto, "pr_ivanov_q1", student_ivanov, quiz1, grade=80.0, status=onto.status_completed)
        _progress(onto, "pr_petrov_q1", student_petrov, quiz1, grade=50.0, status=onto.status_failed)
        _progress(onto, "pr_sidorov_q1", student_sidorov, quiz1, grade=95.0, status=onto.status_completed)

        _progress(onto, "pr_ivanov_pr1", student_ivanov, prac1, grade=70.0, status=onto.status_completed)
        _progress(onto, "pr_sidorov_pr1", student_sidorov, prac1, grade=85.0, status=onto.status_completed)

        _progress(onto, "pr_ivanov_l3_completed", student_ivanov, lec3, status=onto.status_completed)
        _progress(onto, "pr_sidorov_l3_completed", student_sidorov, lec3, status=onto.status_completed)

        _progress(onto, "pr_ivanov_q2", student_ivanov, quiz2, grade=75.0, status=onto.status_completed)
        _progress(onto, "pr_sidorov_q2", student_sidorov, quiz2, grade=90.0, status=onto.status_completed)

        _progress(onto, "pr_ivanov_pr2", student_ivanov, prac2, grade=65.0, status=onto.status_completed)
        _progress(onto, "pr_sidorov_pr2", student_sidorov, prac2, grade=80.0, status=onto.status_completed)

        _progress(onto, "pr_sidorov_l4_completed", student_sidorov, lec4, status=onto.status_completed)
        _progress(onto, "pr_sidorov_q3", student_sidorov, quiz3, grade=75.0, status=onto.status_completed)
        _progress(onto, "pr_sidorov_pr3", student_sidorov, prac3, grade=70.0, status=onto.status_completed)

        # --- Песочница методиста: единственный тестовый студент ---
        sb = onto.SandboxStudent("student_sandbox")
        sb.label = ["Песочница"]
        sb.belongs_to_group = [grp_standard]

        # CurrentTime подставит enricher при reasoning; но для корректной валидации
        # онтологии (disjointness + load через Pellet) оставим заглушку.
        onto.CurrentTime("current_time_ind").has_value = datetime.datetime.utcnow()


def _progress(
    onto: Any,
    pr_id: str,
    student: Any,
    element: Any,
    *,
    grade: float | None = None,
    status: Any | None = None,
) -> Any:
    pr = onto.ProgressRecord(pr_id)
    pr.refers_to_element = [element]
    if grade is not None:
        pr.has_grade = [grade]
    if status is not None:
        pr.has_status = [status]
    pr.started_at = [datetime.datetime.now()]
    existing = list(getattr(student, "has_progress_record", []) or [])
    existing.append(pr)
    student.has_progress_record = existing
    return pr


def build_and_save() -> str:
    """Построить сценарий в изолированном мире и сохранить в ontologies/scenarios/."""
    _, onto = load_tbox_in_isolated_world()
    build(onto)
    return save_scenario(onto, "happy_path.owl")


if __name__ == "__main__":
    path = build_and_save()
    print(f"Happy-path ABox сохранён: {path}")
