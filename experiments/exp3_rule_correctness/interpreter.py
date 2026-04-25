"""Независимый Python-интерпретатор политик доступа

Для каждого из 9 типов правил делает прямую проверку условий на ABox
без Pellet и SWRL, возвращает ту же access matrix, что должен выдать
резонер плюс AccessService.

Используется как ground truth: накладываем матрицу системы на матрицу
интерпретатора, accuracy = доля совпадений per rule_type. Расхождение
указывает либо на баг SWRL-шаблона, либо на баг интерпретатора —
оба случая методологически ценны

Намеренно НЕ использует SWRL-резонер из owlready2, только чтение свойств
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

from core.enums import RuleType


def interpret_satisfies(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None = None) -> bool:
    """True, если студент удовлетворяет политике по прямой проверке условий"""
    rule_type = _get(policy, "rule_type")
    handler = _HANDLERS.get(rule_type)
    if handler is None:
        return False
    return handler(onto, student, policy, now=now)


def interpret_is_available(
    onto: Any,
    student: Any,
    element: Any,
    *,
    now: dt.datetime | None = None,
    parent_map: dict[str, Any] | None = None,
) -> bool:
    """True, если элемент доступен студенту через мета-правило, default-deny и каскад"""
    if parent_map is None:
        parent_map = _build_parent_map(onto)

    active_policies = [p for p in getattr(element, "has_access_policy", []) or [] if _get(p, "is_active", True)]
    if active_policies:
        if not any(interpret_satisfies(onto, student, p, now=now) for p in active_policies):
            return False

    parent = parent_map.get(element.name)
    if parent is None:
        return True
    return interpret_is_available(onto, student, parent, now=now, parent_map=parent_map)


def build_ground_truth_matrix(
    onto: Any,
    course_id: str,
    *,
    now: dt.datetime | None = None,
) -> dict[tuple[str, str], bool]:
    """Для всех (student × element in course) возвращает ожидаемое is_available"""
    course = onto.search_one(iri=f"*{course_id}", type=onto.Course)
    if course is None:
        raise KeyError(f"Курс {course_id} не найден")
    elements = _collect_course_elements(course)
    students = list(onto.Student.instances())
    parent_map = _build_parent_map(onto)
    matrix: dict[tuple[str, str], bool] = {}
    for st in students:
        # Расширяем has_competency: завершённые assessors дают прямые
        # компетенции, иерархия is_subcompetency_of раскрывается транзитивно
        _expand_competencies(onto, st)
        for el in elements:
            matrix[(st.name, el.name)] = interpret_is_available(
                onto, st, el, now=now, parent_map=parent_map
            )
    return matrix


def dominant_rule_type(element: Any) -> str | None:
    """Тип правила, отвечающего за доступ к элементу; None — default-allow

    Для композитов возвращает 'and_combination' / 'or_combination' (корневой тип).
    Если политик несколько — первая активная
    """
    for policy in getattr(element, "has_access_policy", []) or []:
        if _get(policy, "is_active", True):
            return _get(policy, "rule_type")
    return None


# Обработчики по типам правил


def _check_completion(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    target = _get(policy, "targets_element")
    if target is None:
        return False
    for pr in getattr(student, "has_progress_record", []) or []:
        if _same(_get(pr, "refers_to_element"), target) and _status_name(pr) == "status_completed":
            return True
    return False


def _check_grade(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    target = _get(policy, "targets_element")
    threshold = _get(policy, "passing_threshold")
    if target is None or threshold is None:
        return False
    for pr in getattr(student, "has_progress_record", []) or []:
        if not _same(_get(pr, "refers_to_element"), target):
            continue
        grade = _get(pr, "has_grade")
        if grade is not None and grade >= threshold:
            return True
    return False


def _check_viewed(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    target = _get(policy, "targets_element")
    if target is None:
        return False
    # Шаблон 3 + шаблон 3b: viewed или completed засчитывается
    for pr in getattr(student, "has_progress_record", []) or []:
        if not _same(_get(pr, "refers_to_element"), target):
            continue
        status = _status_name(pr)
        if status in ("status_viewed", "status_completed"):
            return True
    return False


def _check_competency(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    required = _get(policy, "targets_competency")
    if required is None:
        return False
    targets = required if isinstance(required, Iterable) and not _is_entity(required) else [required]
    student_comps = list(getattr(student, "has_competency", []) or [])
    for req in targets:
        if any(_same(c, req) for c in student_comps):
            return True
    return False


def _check_date(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    vf = _get(policy, "valid_from")
    vu = _get(policy, "valid_until")
    if vf is None or vu is None:
        return False
    point = now or dt.datetime.utcnow()
    return vf <= point <= vu


def _check_group(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    group = _get(policy, "restricted_to_group")
    if group is None:
        return False
    return any(_same(g, group) for g in getattr(student, "belongs_to_group", []) or [])


def _check_aggregate(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    fn = _get(policy, "aggregate_function", "AVG")
    threshold = _get(policy, "passing_threshold")
    elements = list(getattr(policy, "aggregate_elements", []) or [])
    if not elements or threshold is None:
        return False
    grades: list[float] = []
    for el in elements:
        for pr in getattr(student, "has_progress_record", []) or []:
            if _same(_get(pr, "refers_to_element"), el):
                g = _get(pr, "has_grade")
                if g is not None:
                    grades.append(float(g))
                break
    if not grades:
        return False
    if fn == "AVG":
        value = sum(grades) / len(grades)
    elif fn == "SUM":
        value = sum(grades)
    elif fn == "COUNT":
        value = len(grades)
    else:
        return False
    return value >= threshold


def _check_and(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    subs = list(getattr(policy, "has_subpolicy", []) or [])
    if len(subs) < 2:
        return False
    return all(interpret_satisfies(onto, student, sub, now=now) for sub in subs)


def _check_or(onto: Any, student: Any, policy: Any, *, now: dt.datetime | None) -> bool:
    subs = list(getattr(policy, "has_subpolicy", []) or [])
    if not subs:
        return False
    return any(interpret_satisfies(onto, student, sub, now=now) for sub in subs)


_HANDLERS = {
    RuleType.COMPLETION.value: _check_completion,
    RuleType.GRADE.value: _check_grade,
    RuleType.VIEWED.value: _check_viewed,
    RuleType.COMPETENCY.value: _check_competency,
    RuleType.DATE.value: _check_date,
    RuleType.GROUP.value: _check_group,
    RuleType.AGGREGATE.value: _check_aggregate,
    RuleType.AND.value: _check_and,
    RuleType.OR.value: _check_or,
}


# Вспомогательные функции


def _get(obj: Any, prop: str, default: Any = None) -> Any:
    value = getattr(obj, prop, None)
    if value is None:
        return default
    if isinstance(value, list):
        return value[0] if value else default
    return value


def _status_name(pr: Any) -> str | None:
    status = _get(pr, "has_status")
    if status is None:
        return None
    return getattr(status, "name", str(status))


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    return getattr(a, "name", id(a)) == getattr(b, "name", id(b))


def _is_entity(obj: Any) -> bool:
    return hasattr(obj, "iri")


def _build_parent_map(onto: Any) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for parent in list(onto.Course.instances()) + list(onto.Module.instances()):
        children = list(getattr(parent, "has_module", []) or []) + list(
            getattr(parent, "contains_activity", []) or []
        )
        for child in children:
            mapping[child.name] = parent
    return mapping


def _collect_course_elements(course: Any) -> list[Any]:
    elements: list[Any] = [course]
    seen: set[str] = {course.name}

    def walk(node: Any) -> None:
        for m in getattr(node, "has_module", []) or []:
            if m.name not in seen:
                elements.append(m)
                seen.add(m.name)
                walk(m)
        for a in getattr(node, "contains_activity", []) or []:
            if a.name not in seen:
                elements.append(a)
                seen.add(a.name)
                walk(a)

    walk(course)
    return elements


def _expand_competencies(onto: Any, student: Any) -> None:
    """Расширить has_competency: grants-on-completion + транзитивная иерархия

    Мутирует student.has_competency: добавляет компетенции за завершённые
    assesses-элементы и раскрывает вверх по is_subcompetency_of
    """
    owned: set[str] = {c.name for c in getattr(student, "has_competency", []) or []}
    owned_objs = {c.name: c for c in getattr(student, "has_competency", []) or []}

    # Завершение элементов с assesses → получение компетенции
    for pr in getattr(student, "has_progress_record", []) or []:
        if _status_name(pr) != "status_completed":
            continue
        el = _get(pr, "refers_to_element")
        if el is None:
            continue
        for c in getattr(el, "assesses", []) or []:
            if c.name not in owned:
                owned.add(c.name)
                owned_objs[c.name] = c

    # Транзитивное замыкание через is_subcompetency_of
    changed = True
    while changed:
        changed = False
        for name in list(owned):
            c = owned_objs[name]
            for parent in getattr(c, "is_subcompetency_of", []) or []:
                if parent.name not in owned:
                    owned.add(parent.name)
                    owned_objs[parent.name] = parent
                    changed = True

    student.has_competency = list(owned_objs.values())
