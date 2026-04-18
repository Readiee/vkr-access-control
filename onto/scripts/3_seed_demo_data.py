"""Заполнение ABox демонстрационными данными.

Загружает онтологию с SWRL-правилами и создаёт тестовых индивидов:
студента, методиста, курс с модулями, тест, политику доступа
и запись о прохождении — для проверки логического вывода.

Результат сохраняется в ontologiesdemo_knowledge_base.owl.

Использование:
    python 3_seed_demo_data.py
"""
from owlready2 import get_ontology
import datetime

onto = get_ontology("file://../ontologies/edu_ontology_with_rules.owl").load()

with onto:
    # ------------------------------------------------------------------
    # Пользователи
    # ------------------------------------------------------------------
    student_ivanov        = onto.Student("student_ivanov")
    methodologist_smirnov = onto.Methodologist("methodologist_smirnov")

    # ------------------------------------------------------------------
    # Структура курса
    # ------------------------------------------------------------------
    course_python_basics = onto.Course("course_python_basics")
    module_1_intro       = onto.Module("module_1_intro")
    module_2_advanced    = onto.Module("module_2_advanced")
    test_1_syntax        = onto.Test("test_1_syntax")
    comp_basic_syntax    = onto.Competency("comp_basic_syntax")

    course_python_basics.has_module          = [module_1_intro, module_2_advanced]
    module_1_intro.contains_element          = [test_1_syntax]
    module_1_intro.is_required               = [True]
    module_2_advanced.is_required            = [True]
    test_1_syntax.assesses                   = [comp_basic_syntax]
    test_1_syntax.is_required                = [True]

    # ------------------------------------------------------------------
    # Политика доступа: module_2 требует сдачи test_1 на оценку >= 75
    # ------------------------------------------------------------------
    policy_module2_requires_test1 = onto.AccessPolicy("policy_module2_requires_test1")
    policy_module2_requires_test1.has_author      = [methodologist_smirnov]
    policy_module2_requires_test1.targets_element = [test_1_syntax]
    policy_module2_requires_test1.rule_type       = ["grade_required"]
    policy_module2_requires_test1.passing_threshold = [75.0]
    policy_module2_requires_test1.is_active       = [True]

    module_2_advanced.has_access_policy = [policy_module2_requires_test1]

    # ------------------------------------------------------------------
    # Запись о прогрессе: студент получил 80 баллов (> порога 75) → вывод сработает
    # ------------------------------------------------------------------
    pr1 = onto.ProgressRecord("pr_ivanov_test_1")
    pr1.refers_to_element = [test_1_syntax]
    pr1.has_grade          = [80.0]
    pr1.started_at         = [datetime.datetime.now()]

    student_ivanov.has_progress_record = [pr1]

onto.save(file="../ontologies/demo_knowledge_base.owl", format="rdfxml")
print("Демо-данные успешно добавлены и сохранены в demo_knowledge_base.owl")
