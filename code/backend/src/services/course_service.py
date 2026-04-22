import logging
from typing import List, Optional, Any, Dict
from schemas.schemas import CourseElement, CourseSyncPayload
from core.enums import RuleType, ElementType, ProgressStatus
from services.ontology_core import OntologyCore
from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)


def _label_or_id(obj: Any) -> str:
    if obj is None:
        return ""
    return obj.label[0] if getattr(obj, "label", None) else obj.name


_AGG_FN_LABEL = {"AVG": "Средний балл", "SUM": "Сумма баллов", "COUNT": "Количество сданных"}


def _describe_policy_auto(pol: Any) -> str:
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
        parts = [_describe_policy_auto(sub) for sub in subs]
        return conj.join(parts) if parts else ("И-композит" if rt == "and_combination" else "ИЛИ-композит")
    return rt or pol.name


def _policy_display_name(pol: Any) -> str:
    """Manual label первым, auto-generated — fallback. Методист может дать
    правилу своё имя; по умолчанию показываем описание по типу + полям."""
    label = getattr(pol, "label", None)
    if label:
        return label[0]
    return _describe_policy_auto(pol)


def _serialize_policy(pol: Any, include_subpolicies_detail: bool = True) -> Dict[str, Any]:
    """Подробное представление политики для UI: человечные имена + развёрнутые
    подусловия у композитов. Поле subpolicies_detail — только на верхнем
    уровне (чтобы не уходить в бесконечную вложенность)."""
    subpolicies = list(getattr(pol, "has_subpolicy", []) or [])
    aggregate_elems = list(getattr(pol, "aggregate_elements", []) or [])
    target_el = get_owl_prop(pol, "targets_element")
    target_comp = get_owl_prop(pol, "targets_competency")
    group = get_owl_prop(pol, "restricted_to_group")
    result: Dict[str, Any] = {
        "id": pol.name,
        "name": _policy_display_name(pol),
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
            _serialize_policy(sub, include_subpolicies_detail=False) for sub in subpolicies
        ]
    return result

class CourseService:
    """Сервис управления структурой курса и метаданными онтологии."""

    def __init__(self, core: OntologyCore) -> None:
        self.core = core


    def get_meta(self) -> dict:
        """Возвращает метаданные онтологии (типы правил, статусы, компетенции)."""
        rule_types = [rt.value for rt in RuleType]
        statuses = [ps.value for ps in ProgressStatus]

        competencies: List[dict] = []
        all_comps = self.core.courses.get_all_competencies()
        for comp in all_comps:
                parent_list = getattr(comp, "is_subcompetency_of", [])
                parent_id = parent_list[0].name if parent_list else None
                name = comp.label[0] if comp.label else comp.name
                competencies.append({
                    "id": comp.name, 
                    "name": name,
                    "parent_id": parent_id
                })

        course_elements: List[dict] = []
        all_course_elements = self.core.courses.get_all_elements()
        for el in all_course_elements:
            raw_type = el.type[0] if getattr(el, "type", None) else None
            if not raw_type:
                raw_type = el.__class__.__name__.lower()
            is_req_list = getattr(el, "is_required", [])
            is_req_val = is_req_list[0] if is_req_list else True
            course_elements.append({
                "id": el.name,
                "name": el.label[0] if getattr(el, "label", None) else el.name,
                "type": raw_type,
                "is_required": is_req_val,
            })

        groups: List[dict] = []
        group_cls = getattr(self.core.onto, "Group", None)
        if group_cls is not None:
            for grp in group_cls.instances():
                name = grp.label[0] if getattr(grp, "label", None) else grp.name
                groups.append({"id": grp.name, "name": name})

        return {
            "rule_types": rule_types,
            "statuses": statuses,
            "competencies": competencies,
            "course_elements": course_elements,
            "groups": groups,
        }

    def sync_course_structure(self, course_id: str, payload: CourseSyncPayload) -> dict:
        course = self.core.courses.get_or_create_element(course_id, "Course")
        course.label = [payload.course_name]
        course.is_required = [True]
        
        # Soft Reset курса (удаление только связей)
        for old_module in list(course.has_module):
            old_module.contains_element = []
        course.has_module = []

        # Сборка иерархии по новому payload

        for idx, elem_data in enumerate(payload.elements):
            class_name = elem_data.element_type.capitalize()
            element = self.core.courses.get_or_create_element(elem_data.element_id, class_name)
            
            element.label = [elem_data.name]
            element.type = [elem_data.element_type.lower()]
            element.is_required = [getattr(elem_data, "is_required", True)]
            
            # Неявная или явная сортировка
            final_order = elem_data.order_index if getattr(elem_data, "order_index", None) is not None else idx
            element.order_index = [final_order]

            if elem_data.parent_id:
                parent = self.core.courses.find_by_id(elem_data.parent_id)
                if not parent:
                    parent = self.core.courses.get_or_create_element(elem_data.parent_id, "CourseStructure")

                if elem_data.element_type == ElementType.MODULE.value:
                    if element not in getattr(parent, "has_module", []):
                        parent.has_module.append(element)
                else:
                    if element not in getattr(parent, "contains_element", []):
                        parent.contains_element.append(element)
                

        self.core.save()
        self.core.cache.invalidate_verification(course.name)
        return {"status": "success", "course_id": course.name, "synced_elements_count": len(payload.elements)}

    def get_course_tree(self, course_id: str) -> List[dict]:
        """Возвращает иерархию курса с прикрепленными политиками."""
        course = self.core.courses.find_by_id(course_id)
        if not course:
            return []

        def build_node(node_obj, node_type_override=None):
            node_id = node_obj.name
            node_name = node_obj.label[0] if getattr(node_obj, "label", None) else node_id
            raw_type = node_type_override or node_obj.__class__.__name__.lower()
            
            policies = []
            for pol in getattr(node_obj, "has_access_policy", []):
                policies.append(_serialize_policy(pol))

            if raw_type == ElementType.COURSE.value:
                children_objs = getattr(node_obj, "has_module", [])
            elif raw_type == ElementType.MODULE.value:
                children_objs = getattr(node_obj, "contains_element", [])
            else:
                children_objs = []

            children_objs = sorted(
                children_objs, 
                key=lambda x: getattr(x, "order_index", [999])[0] if getattr(x, "order_index", []) else 999 # элементы без индекса уходят в конец
            )

            children = [build_node(child) for child in children_objs]

            return {
                "key": node_id,
                "data": {
                    "id": node_id, 
                    "name": node_name, 
                    "type": get_owl_prop(node_obj, "type", raw_type), 
                    "policies": policies,
                    "is_required": get_owl_prop(node_obj, "is_required", True)
                },
                "children": children
            }

        return [build_node(course, ElementType.COURSE.value)]
