"""Каталог SWRL-правил

Двухуровневая семантика:
  - Ступень 1: атомарные и композитные шаблоны выводят satisfies(?s, ?p) —
    условие политики выполнено для студента
  - Ступень 2: единое мета-правило превращает satisfies в is_available_for

Загружает TBox из edu_ontology.owl, встраивает правила, сохраняет
edu_ontology_with_rules.owl
"""
from owlready2 import get_ontology, Imp

onto = get_ontology("file://../ontologies/edu_ontology.owl").load()

with onto:
    # -- H-1. Наследование компетенций (вспомогательное правило) --
    # Распространяет has_competency вверх по иерархии is_subcompetency_of
    rule_competency_inheritance = Imp()
    rule_competency_inheritance.set_as_rule("""
        Student(?s), has_competency(?s, ?sub), is_subcompetency_of(?sub, ?parent)
        -> has_competency(?s, ?parent)
    """)

    # -- H-2. Выдача компетенций через прохождение --
    # Если студент завершил элемент, оценивающий компетенцию, он её получает.
    # Дальше H-1 транзитивно добавит родительские компетенции
    rule_competency_from_progress = Imp()
    rule_competency_from_progress.set_as_rule("""
        Student(?s), has_progress_record(?s, ?pr),
        refers_to_element(?pr, ?el), has_status(?pr, status_completed),
        assesses(?el, ?c)
        -> has_competency(?s, ?c)
    """)

    # -- H-3. Наследование членства в группе вверх по is_subgroup_of --
    # Если студент в подгруппе, он автоматически считается членом всех
    # родительских групп. is_subgroup_of транзитивен на уровне TBox, поэтому
    # одно правило покрывает любую глубину иерархии
    rule_group_inheritance = Imp()
    rule_group_inheritance.set_as_rule("""
        Student(?s), belongs_to_group(?s, ?g), is_subgroup_of(?g, ?parent)
        -> belongs_to_group(?s, ?parent)
    """)

    # -- Шаблон 3b — viewed_required через completion --
    # Если элемент завершён, он автоматически считается просмотренным.
    # Второе правило с той же головой satisfies даёт дизъюнкцию (rule 3
    # «через status_viewed» ∨ rule 3b «через status_completed»)
    rule_viewed_via_completed = Imp()
    rule_viewed_via_completed.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "viewed_required"),
        targets_element(?p, ?target),
        Student(?s), has_progress_record(?s, ?pr),
        refers_to_element(?pr, ?target), has_status(?pr, status_completed)
        -> satisfies(?s, ?p)
    """)

    # -- Ступень 1. Атомарные шаблоны (выводят satisfies) --

    # Шаблон 1 — completion_required
    rule_completion = Imp()
    rule_completion.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "completion_required"),
        targets_element(?p, ?target),
        Student(?s), has_progress_record(?s, ?pr),
        refers_to_element(?pr, ?target), has_status(?pr, status_completed)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 2 — grade_required
    rule_grade = Imp()
    rule_grade.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "grade_required"),
        targets_element(?p, ?target), passing_threshold(?p, ?th),
        Student(?s), has_progress_record(?s, ?pr),
        refers_to_element(?pr, ?target), has_grade(?pr, ?g),
        greaterThanOrEqual(?g, ?th)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 3 — viewed_required
    rule_viewed = Imp()
    rule_viewed.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "viewed_required"),
        targets_element(?p, ?target),
        Student(?s), has_progress_record(?s, ?pr),
        refers_to_element(?pr, ?target), has_status(?pr, status_viewed)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 4 — competency_required (иерархия через H-1)
    rule_competency = Imp()
    rule_competency.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "competency_required"),
        targets_competency(?p, ?req_comp),
        Student(?s), has_competency(?s, ?req_comp)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 5 — date_restricted (CurrentTime подкладывает текущее время перед прогоном)
    rule_date = Imp()
    rule_date.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "date_restricted"),
        valid_from(?p, ?from), valid_until(?p, ?until),
        CurrentTime(?now_ind), has_value(?now_ind, ?now),
        greaterThanOrEqual(?now, ?from), lessThanOrEqual(?now, ?until),
        Student(?s)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 8 — group_restricted
    rule_group = Imp()
    rule_group.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "group_restricted"),
        restricted_to_group(?p, ?g),
        Student(?s), belongs_to_group(?s, ?g)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 9 — aggregate_required (AggregateFact считается до прогона, SWRL только сравнивает с порогом)
    rule_aggregate = Imp()
    rule_aggregate.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "aggregate_required"),
        passing_threshold(?p, ?th),
        AggregateFact(?f), for_policy(?f, ?p), for_student(?f, ?s),
        computed_value(?f, ?val),
        greaterThanOrEqual(?val, ?th)
        -> satisfies(?s, ?p)
    """)

    # -- Ступень 1. Композитные шаблоны --

    # Шаблон 7 — or_combination (хотя бы одна подполитика выполнена)
    rule_or = Imp()
    rule_or.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "or_combination"),
        has_subpolicy(?p, ?sub),
        Student(?s), satisfies(?s, ?sub)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 6 — and_combination (бинарный); DifferentFrom обязателен —
    # иначе SWRL унифицирует ?sub1=?sub2 и AND превращается в OR
    rule_and_2 = Imp()
    rule_and_2.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "and_combination"),
        has_subpolicy(?p, ?sub1), has_subpolicy(?p, ?sub2), DifferentFrom(?sub1, ?sub2),
        Student(?s), satisfies(?s, ?sub1), satisfies(?s, ?sub2)
        -> satisfies(?s, ?p)
    """)

    # Шаблон 6b — and_combination (3-арный, для плоских AND из 3 операндов)
    rule_and_3 = Imp()
    rule_and_3.set_as_rule("""
        AccessPolicy(?p), is_active(?p, true), rule_type(?p, "and_combination"),
        has_subpolicy(?p, ?sub1), has_subpolicy(?p, ?sub2), has_subpolicy(?p, ?sub3),
        DifferentFrom(?sub1, ?sub2), DifferentFrom(?sub2, ?sub3), DifferentFrom(?sub1, ?sub3),
        Student(?s), satisfies(?s, ?sub1), satisfies(?s, ?sub2), satisfies(?s, ?sub3)
        -> satisfies(?s, ?p)
    """)

    # -- Ступень 2. Мета-правило (satisfies → is_available_for) --
    rule_meta_available = Imp()
    rule_meta_available.set_as_rule("""
        CourseStructure(?el), has_access_policy(?el, ?p), is_active(?p, true),
        Student(?s), satisfies(?s, ?p)
        -> is_available_for(?el, ?s)
    """)

onto.save(file="../ontologies/edu_ontology_with_rules.owl", format="rdfxml")
print("SWRL-каталог встроён: edu_ontology_with_rules.owl")
print("  ступень 1: 10 шаблонов (1-3, 3b, 4-5, 6 binary, 6 ternary, 7, 8, 9) + H-1 + H-2 + H-3")
print("  ступень 2: 1 мета-правило")
