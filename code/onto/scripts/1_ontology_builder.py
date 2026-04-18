"""Построение TBox онтологии образовательного процесса.

Определяет классы, объектные и атрибутивные свойства,
сохраняет результат в ontologiesedu_ontology.owl.

Использование:
    python 1_ontology_builder.py
"""
from owlready2 import get_ontology, Thing, ObjectProperty, DataProperty, TransitiveProperty
import os
import datetime

onto_file = "../ontologies/edu_ontology.owl"
if os.path.exists(onto_file):
    os.remove(onto_file)

onto = get_ontology("http://example.org/edu_ontology.owl")
with onto:
    # ------------------------------------------------------------------
    # 1. Классы
    # ------------------------------------------------------------------

    # Пользователи
    class User(Thing): pass
    class Student(User): pass
    class Teacher(User): pass
    class Methodologist(User): pass

    # Структура курса
    class CourseStructure(Thing): pass
    class Course(CourseStructure): pass
    class Module(CourseStructure): pass

    class EducationalElement(CourseStructure): pass
    class Lecture(EducationalElement): pass
    class Test(EducationalElement): pass
    class Assignment(EducationalElement): pass
    class Practice(EducationalElement): pass

    # Вспомогательные классы
    class Status(Thing): pass
    status_passed = Status("status_passed")
    status_viewed      = Status("status_viewed")
    status_completed   = Status("status_completed")
    status_failed      = Status("status_failed")

    class ProgressRecord(Thing): pass   # Факт взаимодействия студента с элементом
    class Competency(Thing): pass
    class AccessPolicy(Thing): pass     # Узел правила доступа (Reification)

    # ------------------------------------------------------------------
    # 2. Объектные свойства (связи между индивидами)
    # ------------------------------------------------------------------


    class is_contained_in_course(ObjectProperty):
        """Модуль содержится в курсе."""
        domain = [Module];  range = [Course]

    class has_module(ObjectProperty):
        """Курс содержит модули."""
        domain = [Course];  range = [Module]
        inverse_property = is_contained_in_course

    class is_contained_in_module(ObjectProperty):
        """Элемент содержится в модуле."""
        domain = [EducationalElement];  range = [Module]

    class contains_element(ObjectProperty):
        """Модуль содержит учебные элементы."""
        domain = [Module];  range = [EducationalElement]
        inverse_property = is_contained_in_module

    class has_progress_record(ObjectProperty):
        """Студент имеет записи о прохождении."""
        domain = [Student];  range = [ProgressRecord]

    class refers_to_student(ObjectProperty):
        """Запись прогресса относится к студенту."""
        domain = [ProgressRecord]; range = [Student]
        inverse_property = has_progress_record

    class refers_to_element(ObjectProperty):
        """Запись прогресса относится к элементу курса."""
        domain = [ProgressRecord]; range = [CourseStructure]

    class has_status(ObjectProperty):
        """Текущий статус записи прогресса."""
        domain = [ProgressRecord];  range = [Status]

    class assesses(ObjectProperty):
        """Тест или задание проверяет компетенцию."""
        domain = [CourseStructure];  range = [Competency]

    class has_competency(ObjectProperty):
        """Студент владеет компетенцией."""
        domain = [Student]; range = [Competency]

    class targets_competency(ObjectProperty):
        """Политика требует наличие компетенции."""
        domain = [AccessPolicy];  range = [Competency]

    class has_access_policy(ObjectProperty):
        """Элемент курса защищён политикой доступа."""
        domain = [CourseStructure];  range = [AccessPolicy]

    class targets_element(ObjectProperty):
        """Политика нацелена на конкретный элемент."""
        domain = [AccessPolicy];  range = [CourseStructure]

    class has_author(ObjectProperty):
        """Автор (методист), создавший политику."""
        domain = [AccessPolicy];  range = [Methodologist]

    class is_subcompetency_of(ObjectProperty, TransitiveProperty):
        """Иерархия компетенций: мастерство дочерней дает мастерство родительской."""
        domain = [Competency];  range = [Competency]

    # ------------------------------------------------------------------
    # 3. Атрибутивные свойства (скалярные значения)
    # ------------------------------------------------------------------

    class is_active(DataProperty):
        """Флаг активности политики."""
        domain = [AccessPolicy];  range = [bool]

    class is_required(DataProperty):
        """Флаг обязательности прохождения элемента для Roll-up."""
        domain = [CourseStructure];  range = [bool]

    class order_index(DataProperty):
        """Порядковый номер элемента в иерархии."""
        domain = [CourseStructure];  range = [int]

    class rule_type(DataProperty):
        """Тип логики правила: grade_required, completion_required и т.д."""
        domain = [AccessPolicy];  range = [str]

    class passing_threshold(DataProperty):
        """Минимальный балл для выполнения условия grade_required."""
        domain = [AccessPolicy];  range = [float]

    class has_grade(DataProperty):
        """Оценка студента за элемент."""
        domain = [ProgressRecord];  range = [float]

    class failed_attempts_count(DataProperty):
        """Количество неудачных попыток."""
        domain = [ProgressRecord];  range = [int]

    class started_at(DataProperty):
        """Время начала прохождения."""
        domain = [ProgressRecord];  range = [datetime.datetime]

    class completed_at(DataProperty):
        """Время успешного завершения."""
        domain = [ProgressRecord];  range = [datetime.datetime]

onto.save(file="../ontologies/edu_ontology.owl", format="rdfxml")
print("Онтология успешно сгенерирована и сохранена в edu_ontology.owl")
