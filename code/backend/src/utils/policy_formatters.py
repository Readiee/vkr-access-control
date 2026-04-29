"""Человечное отображение политик доступа для UI и отчётов.

Использование: API-слой, VerificationService и AccessService — строят JSON-ответы
с человечными именами правил (методист видит «Завершить лекцию 1», а не идентификаторы).
Модуль утилитарный, без зависимостей на сервисы.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from utils.owl_utils import get_owl_prop, label_or_name


_AGG_FN_LABEL = {"AVG": "Средний балл", "SUM": "Сумма баллов", "COUNT": "Количество сданных"}


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
        return f"Завершить «{label_or_name(target)}»"
    if rt == "viewed_required" and target is not None:
        return f"Просмотреть «{label_or_name(target)}»"
    if rt == "grade_required" and target is not None:
        return f"Оценка ≥ {threshold} за «{label_or_name(target)}»"
    if rt == "competency_required" and comp is not None:
        return f"Компетенция «{label_or_name(comp)}»"
    if rt == "date_restricted":
        vf = get_owl_prop(pol, "valid_from")
        vu = get_owl_prop(pol, "valid_until")
        fmt = lambda d: d.strftime("%d.%m.%Y") if d else "?"
        return f"Доступно {fmt(vf)} – {fmt(vu)}"
    if rt == "group_restricted" and group is not None:
        return f"Только группа «{label_or_name(group)}»"
    if rt == "aggregate_required":
        fn = get_owl_prop(pol, "aggregate_function") or "AVG"
        fn_ru = _AGG_FN_LABEL.get(fn, fn)
        elems = list(getattr(pol, "aggregate_elements", []) or [])
        names = ", ".join(f"«{label_or_name(e)}»" for e in elems)
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


def serialize_policy(
    pol: Any,
    *,
    source_id: Optional[str] = None,
    include_subpolicies_detail: bool = True,
) -> Dict[str, Any]:
    """Единое представление политики: ключи под Pydantic-схему `Policy`
    (включая UI-extras). Параметр `source_id` подставляется в `source_element_id`,
    если он не выведен из has_access_policy. `subpolicies_detail` — только на
    верхнем уровне, чтобы не уходить в бесконечную вложенность.
    """
    subpolicies = list(getattr(pol, "has_subpolicy", []) or [])
    aggregate_elems = list(getattr(pol, "aggregate_elements", []) or [])
    target_el = get_owl_prop(pol, "targets_element")
    target_comp = get_owl_prop(pol, "targets_competency")
    group = get_owl_prop(pol, "restricted_to_group")
    author = get_owl_prop(pol, "has_author")
    rule_type = get_owl_prop(pol, "rule_type", "") or ""

    result: Dict[str, Any] = {
        "id": pol.name,
        "name": policy_display_name(pol),
        "source_element_id": source_id,
        "rule_type": rule_type,
        "passing_threshold": get_owl_prop(pol, "passing_threshold"),
        "target_element_id": target_el.name if target_el else None,
        "target_element_name": label_or_name(target_el) if target_el else None,
        "target_competency_id": target_comp.name if target_comp else None,
        "target_competency_name": label_or_name(target_comp) if target_comp else None,
        "valid_from": get_owl_prop(pol, "valid_from"),
        "valid_until": get_owl_prop(pol, "valid_until"),
        "restricted_to_group_id": group.name if group else None,
        "restricted_to_group_name": label_or_name(group) if group else None,
        "subpolicy_ids": [s.name for s in subpolicies] or None,
        "aggregate_function": get_owl_prop(pol, "aggregate_function"),
        "aggregate_element_ids": [e.name for e in aggregate_elems] or None,
        "aggregate_element_names": [label_or_name(e) for e in aggregate_elems] or None,
        "is_active": bool(get_owl_prop(pol, "is_active", True)),
        "author_id": author.name if author else "system",
    }
    if include_subpolicies_detail and subpolicies:
        result["subpolicies_detail"] = [
            serialize_policy(sub, include_subpolicies_detail=False) for sub in subpolicies
        ]
    return result
