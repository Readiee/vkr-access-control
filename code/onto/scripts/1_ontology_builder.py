"""Сборка TBox онтологии управления доступом к образовательному контенту.

Определяет классы, объектные и атрибутивные свойства, аксиомы дизъюнктности
и функциональности. Результат — edu_ontology.owl.
"""
from owlready2 import (
    get_ontology, Thing, ObjectProperty, DataProperty,
    TransitiveProperty, FunctionalProperty, AllDisjoint,
)
import os
import datetime

onto_file = "../ontologies/edu_ontology.owl"
if os.path.exists(onto_file):
    os.remove(onto_file)

onto = get_ontology("http://example.org/edu_ontology.owl")
with onto:
    # ==================================================================
    # 1. КЛАССЫ
    # ==================================================================

    # Пользователи
    class User(Thing): pass
    class Student(User): pass
    class Teacher(User): pass
    class Methodologist(User): pass

    # Группы студентов для правил group_restricted
    class Group(Thing): pass

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
    status_passed      = Status("status_passed")
    status_viewed      = Status("status_viewed")
    status_completed   = Status("status_completed")
    status_failed      = Status("status_failed")

    class ProgressRecord(Thing): pass
    class Competency(Thing): pass
    class AccessPolicy(Thing): pass

    class CurrentTime(Thing): pass      # одиночный индивид current_time_ind, SWRL не имеет now()
    class AggregateFact(Thing): pass    # результат агрегата per (student, policy), SWRL не умеет aggregates

    # ==================================================================
    # 2. ОБЪЕКТНЫЕ СВОЙСТВА
    # ==================================================================

    # --- Иерархия курса ---
    class is_contained_in_course(ObjectProperty):
        domain = [Module]; range = [Course]

    class has_module(ObjectProperty):
        domain = [Course]; range = [Module]
        inverse_property = is_contained_in_course

    class is_contained_in_module(ObjectProperty):
        domain = [EducationalElement]; range = [Module]

    class contains_element(ObjectProperty):
        domain = [Module]; range = [EducationalElement]
        inverse_property = is_contained_in_module

    # --- Прогресс ---
    class has_progress_record(ObjectProperty):
        domain = [Student]; range = [ProgressRecord]

    class refers_to_student(ObjectProperty):
        domain = [ProgressRecord]; range = [Student]
        inverse_property = has_progress_record

    class refers_to_element(ObjectProperty):
        domain = [ProgressRecord]; range = [CourseStructure]

    class has_status(ObjectProperty):
        domain = [ProgressRecord]; range = [Status]

    # --- Компетенции ---
    class assesses(ObjectProperty):
        domain = [CourseStructure]; range = [Competency]

    class has_competency(ObjectProperty):
        domain = [Student]; range = [Competency]

    class targets_competency(ObjectProperty):
        domain = [AccessPolicy]; range = [Competency]

    class is_subcompetency_of(ObjectProperty, TransitiveProperty):
        domain = [Competency]; range = [Competency]

    # --- Политики ---
    class has_access_policy(ObjectProperty):
        domain = [CourseStructure]; range = [AccessPolicy]

    class targets_element(ObjectProperty):
        domain = [AccessPolicy]; range = [CourseStructure]

    class has_author(ObjectProperty):
        domain = [AccessPolicy]; range = [Methodologist]

    # Композиция политик для AND/OR
    class has_subpolicy(ObjectProperty):
        domain = [AccessPolicy]; range = [AccessPolicy]

    class belongs_to_group(ObjectProperty):
        domain = [Student]; range = [Group]

    class restricted_to_group(ObjectProperty):
        domain = [AccessPolicy]; range = [Group]

    class aggregate_elements(ObjectProperty):
        """Элементы, по оценкам которых считается агрегат (multi-valued)."""
        domain = [AccessPolicy]; range = [CourseStructure]

    class for_student(ObjectProperty, FunctionalProperty):
        domain = [AggregateFact]; range = [Student]

    class for_policy(ObjectProperty, FunctionalProperty):
        domain = [AggregateFact]; range = [AccessPolicy]

    class satisfies(ObjectProperty):
        """Выводится SWRL: студент удовлетворяет условию политики."""
        domain = [Student]; range = [AccessPolicy]

    class is_available_for(ObjectProperty):
        """Выводится SWRL: элемент доступен студенту."""
        domain = [CourseStructure]; range = [Student]

    # ==================================================================
    # 3. АТРИБУТИВНЫЕ СВОЙСТВА
    # ==================================================================
    # legacy-свойства оставлены non-Functional: owlready2 mixin требует
    # scalar API, а код записывает их как prop = [value]. Миграция — вместе
    # с рефакторингом обращений. Новые свойства сразу Functional.

    class is_active(DataProperty):
        domain = [AccessPolicy]; range = [bool]

    class is_required(DataProperty):
        domain = [CourseStructure]; range = [bool]

    class order_index(DataProperty):
        domain = [CourseStructure]; range = [int]

    class rule_type(DataProperty):
        """Один из: completion_required, grade_required, viewed_required, competency_required,
        date_restricted, and_combination, or_combination, group_restricted, aggregate_required."""
        domain = [AccessPolicy]; range = [str]

    class passing_threshold(DataProperty):
        domain = [AccessPolicy]; range = [float]

    class valid_from(DataProperty):
        domain = [AccessPolicy]; range = [datetime.datetime]

    class valid_until(DataProperty):
        domain = [AccessPolicy]; range = [datetime.datetime]

    class has_grade(DataProperty):
        domain = [ProgressRecord]; range = [float]

    class failed_attempts_count(DataProperty):
        domain = [ProgressRecord]; range = [int]

    class started_at(DataProperty):
        domain = [ProgressRecord]; range = [datetime.datetime]

    class completed_at(DataProperty):
        domain = [ProgressRecord]; range = [datetime.datetime]

    class has_value(DataProperty, FunctionalProperty):
        domain = [CurrentTime]; range = [datetime.datetime]

    class aggregate_function(DataProperty, FunctionalProperty):
        """Один из: AVG, SUM, COUNT."""
        domain = [AccessPolicy]; range = [str]

    class computed_value(DataProperty, FunctionalProperty):
        domain = [AggregateFact]; range = [float]

    # ==================================================================
    # 4. АКСИОМЫ ДИЗЪЮНКТНОСТИ
    # ==================================================================

    AllDisjoint([Student, Teacher, Methodologist])
    AllDisjoint([Course, Module, EducationalElement])
    AllDisjoint([Lecture, Test, Assignment, Practice])
    AllDisjoint([
        User, CourseStructure, Group, ProgressRecord,
        Competency, AccessPolicy, Status, CurrentTime, AggregateFact,
    ])

onto.save(file=onto_file, format="rdfxml")
print("TBox сгенерирован: edu_ontology.owl")
print(f"  классов: {len(list(onto.classes()))}")
print(f"  object properties: {len(list(onto.object_properties()))}")
print(f"  data properties: {len(list(onto.data_properties()))}")
