"""Встраивание SWRL-правил доступа в онтологию.

Загружает базовую схему edu_ontology.owl, добавляет объектные свойства
и SWRL-правила логического вывода,
сохраняет результат в ontologies/edu_ontology_with_rules.owl.

Использование:
    python 2_rules_setup.py
"""
from owlready2 import get_ontology, ObjectProperty, Imp, TransitiveProperty

# Загрузка базовой схемы (только TBox, без экземпляров)
onto = get_ontology("file://../ontologies/edu_ontology.owl").load()

with onto:
    # ------------------------------------------------------------------
    # Объектные свойства
    # ------------------------------------------------------------------

    class is_available_for(ObjectProperty):
        """Логически выводимое свойство: элемент курса доступен студенту."""
        domain = [onto.CourseStructure]
        range  = [onto.Student]

    class has_competency(ObjectProperty):
        """Студент владеет компетенцией."""
        domain = [onto.Student]
        range  = [onto.Competency]

    class targets_competency(ObjectProperty):
        """Политика требует наличие компетенции."""
        domain = [onto.AccessPolicy]
        range  = [onto.Competency]

    # Транзитивное свойство для иерархии компетенций
    class is_subcompetency_of(ObjectProperty, TransitiveProperty):
        domain = [onto.Competency]
        range = [onto.Competency]

    # ------------------------------------------------------------------
    # Если студент владеет подкомпетенцией, он владеет и родительской компетенцией.
    # ------------------------------------------------------------------
    rule_competency_inheritance = Imp()
    rule_competency_inheritance.set_as_rule("""
        Student(?s), has_competency(?s, ?sub), is_subcompetency_of(?sub, ?parent)
        -> has_competency(?s, ?parent)
    """)

    # ------------------------------------------------------------------
    # ПРАВИЛО 1 — grade_required
    # Срабатывает, если оценка студента >= порогового значения политики.
    # ------------------------------------------------------------------
    rule_grade_access = Imp()
    rule_grade_access.set_as_rule("""
        CourseStructure(?element), has_access_policy(?element, ?policy), is_active(?policy, true), rule_type(?policy, "grade_required"),
        targets_element(?policy, ?target_elem), passing_threshold(?policy, ?threshold),
        Student(?student), has_progress_record(?student, ?pr), refers_to_element(?pr, ?target_elem),
        has_grade(?pr, ?grade), greaterThanOrEqual(?grade, ?threshold)
        -> is_available_for(?element, ?student)
    """)

    # ------------------------------------------------------------------
    # ПРАВИЛО 2 — completion_required
    # Срабатывает при наличии статуса completed у записи прогресса. Пороговая оценка не важна.
    # ------------------------------------------------------------------
    rule_completion_access = Imp()
    rule_completion_access.set_as_rule("""
        CourseStructure(?element), has_access_policy(?element, ?policy), is_active(?policy, true), rule_type(?policy, "completion_required"),
        targets_element(?policy, ?target_elem),
        Student(?student), has_progress_record(?student, ?pr), refers_to_element(?pr, ?target_elem),
        has_status(?pr, status_completed)
        -> is_available_for(?element, ?student)
    """)

    # ------------------------------------------------------------------
    # ПРАВИЛО 3: Открытие по компетенции (с учетом иерархии!)
    # Если студент имеет ?actual_comp, которая является подкомпетенцией ?req_comp, доступ открывается.
    # ------------------------------------------------------------------
    rule_competency_access = Imp()
    rule_competency_access.set_as_rule("""
        CourseStructure(?element), has_access_policy(?element, ?policy), is_active(?policy, true), rule_type(?policy, "competency_required"),
        targets_competency(?policy, ?req_comp), 
        Student(?student), has_competency(?student, ?actual_comp),
        is_subcompetency_of(?actual_comp, ?req_comp)
        -> is_available_for(?element, ?student)
    """)

    # ------------------------------------------------------------------
    # ПРАВИЛО 4 — viewed_required
    # Срабатывает, если студент открыл (просмотрел) целевой элемент.
    # ------------------------------------------------------------------
    rule_viewed_access = Imp()
    rule_viewed_access.set_as_rule("""
        CourseStructure(?element), has_access_policy(?element, ?policy), is_active(?policy, true), rule_type(?policy, "viewed_required"),
        targets_element(?policy, ?target_elem),
        Student(?student), has_progress_record(?student, ?pr), refers_to_element(?pr, ?target_elem),
        has_status(?pr, status_viewed)
        -> is_available_for(?element, ?student)
    """)

# Сохранение онтологии с встроенными SWRL-правилами
onto.save(file="../ontologies/edu_ontology_with_rules.owl", format="rdfxml")
print("SWRL-правила успешно встроены. Файл сохранён как edu_ontology_with_rules.owl")
