"""Человечное отображение политик доступа для UI и отчётов.

Использование: API-слой, VerificationService и AccessService — строят JSON-ответы
с человечными именами правил (методист видит «Завершить лекцию 1», а не идентификаторы).
Модуль утилитарный, без зависимостей на сервисы.
"""
from __future__ import annotations

from typing import Any, Dict

from utils.owl_utils import get_owl_prop


_AGG_FN_LABEL = {"AVG": "Средний балл", "SUM": "Сумма баллов", "COUNT": "Количество сданных"}


def _label_or_id(obj: Any) -> str:
    if obj is None:
        return ""
    return obj.label[0] if getattr(obj, "label", None) else obj.name


def describe_policy_auto(pol: Any) -> str:
    """Собрать человечное описание правила из его полей — не из rdfs:label.

    Вызывается, если у политики нет ручного label. Для AND/OR рекурсивно
    собирает описания подполитик и склеивает через « и »/« или ».
    """
    rt = get_owl_prop(pol, "rule_type", "") or ""
    target = get_owl_prop(pol, "targets_element")
    comp = get_owl_prop(pol, "targets_competency")
    group = get_owl_prop(pol, "restricted_to_group")
    threshold = get_owl_prop(pol, "passing_threshold")

    if rt == "completion_required" and target is not None:
        return f"Завершить «{_label_or_id(target)}»"
    if rt == "viewed_required" and target is not None:
        return f"Просмотреть «{_label_or_id(target)}»"
    if rt == "grade_required" and target is not None:
        return f"Оценка ≥ {threshold} за «{_label_or_id(target)}»"
    if rt == "competency_required" and comp is not None:
        return f"Компетенция «{_label_or_id(comp)}»"
    if rt == "date_restricted":
        vf = get_owl_prop(pol, "valid_from")
        vu = get_owl_prop(pol, "valid_until")
        fmt = lambda d: d.strftime("%d.%m.%Y") if d else "?"
        return f"Доступно {fmt(vf)} – {fmt(vu)}"
    if rt == "group_restricted" and group is not None:
        return f"Только группа «{_label_or_id(group)}»"
    if rt == "aggregate_required":
        fn = get_owl_prop(pol, "aggregate_function") or "AVG"
        fn_ru = _AGG_FN_LABEL.get(fn, fn)
        elems = list(getattr(pol, "aggregate_elements", []) or [])
        names = ", ".join(f"«{_label_or_id(e)}»" for e in elems)
        return f"{fn_ru} по {names} ≥ {threshold}" if names else f"{fn_ru} ≥ {threshold}"
    if rt in ("and_combination", "or_combination"):
        subs = list(getattr(pol, "has_subpolicy", []) or [])
        conj = " И " if rt == "and_combination" else " ИЛИ "
        parts = [describe_policy_auto(sub) for sub in subs]
        return conj.join(parts) if parts else ("И-композит" if rt == "and_combination" else "ИЛИ-композит")
    return rt or pol.name


def policy_display_name(pol: Any) -> str:
    """Manual label первым, auto-generated — fallback.

    Методист может дать правилу своё имя через rdfs:label; по умолчанию
    показываем описание по типу + полям.
    """
    label = getattr(pol, "label", None)
    if label:
        return label[0]
    return describe_policy_auto(pol)


def serialize_policy(pol: Any, include_subpolicies_detail: bool = True) -> Dict[str, Any]:
    """Подробное представление политики для UI: человечные имена + развёрнутые
    подусловия у композитов. Поле subpolicies_detail — только на верхнем
    уровне (чтобы не уходить в бесконечную вложенность).
    """
    subpolicies = list(getattr(pol, "has_subpolicy", []) or [])
    aggregate_elems = list(getattr(pol, "aggregate_elements", []) or [])
    target_el = get_owl_prop(pol, "targets_element")
    target_comp = get_owl_prop(pol, "targets_competency")
    group = get_owl_prop(pol, "restricted_to_group")
    result: Dict[str, Any] = {
        "id": pol.name,
        "name": policy_display_name(pol),
        "rule_type": get_owl_prop(pol, "rule_type", ""),
        "passing_threshold": get_owl_prop(pol, "passing_threshold"),
        "competency_id": target_comp.name if target_comp else None,
        "competency_name": _label_or_id(target_comp) if target_comp else None,
        "target_element_id": target_el.name if target_el else None,
        "target_element_name": _label_or_id(target_el) if target_el else None,
        "valid_from": get_owl_prop(pol, "valid_from"),
        "valid_until": get_owl_prop(pol, "valid_until"),
        "restricted_to_group_id": group.name if group else None,
        "restricted_to_group_name": _label_or_id(group) if group else None,
        "subpolicy_ids": [s.name for s in subpolicies],
        "aggregate_function": get_owl_prop(pol, "aggregate_function"),
        "aggregate_element_ids": [e.name for e in aggregate_elems],
        "aggregate_element_names": [_label_or_id(e) for e in aggregate_elems],
        "is_active": get_owl_prop(pol, "is_active", True),
    }
    if include_subpolicies_detail and subpolicies:
        result["subpolicies_detail"] = [
            serialize_policy(sub, include_subpolicies_detail=False) for sub in subpolicies
        ]
    return result
