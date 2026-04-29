"""Человекочитаемое представление политик доступа."""
from __future__ import annotations

from typing import Any, Dict, Optional

from utils.owl_utils import get_owl_prop, label_or_name


def describe_policy_auto(pol: Any) -> str:
    """Описание правила из его полей; для AND/OR рекурсивно через handler.describe."""
    from services.rule_handlers import REGISTRY
    rt = get_owl_prop(pol, "rule_type", "") or ""
    handler = REGISTRY.get(rt)
    return handler.describe(pol) if handler else (rt or pol.name)


def policy_display_name(pol: Any) -> str:
    """rdfs:label, если задан; иначе авто-описание по полям."""
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
    """Представление политики под Pydantic-схему `Policy`.

    `source_id` подставляется в source_element_id, если он не выводится через
    has_access_policy. `subpolicies_detail` разворачивается только на верхнем
    уровне — иначе бесконечная вложенность.
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
