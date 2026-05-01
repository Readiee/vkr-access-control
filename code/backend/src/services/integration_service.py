import logging
from typing import Any, List

from core.enums import (
    COURSE_STRUCTURE_OWL_CLASS,
    ELEMENT_TYPE_TO_OWL_CLASS,
    ElementType,
    ProgressStatus,
    RuleType,
)
from schemas import CourseSyncPayload
from core.cache_manager import CacheManager
from core.ontology_core import OntologyCore
from services.verification import VerificationService
from utils.owl_utils import get_owl_prop, label_or_name
from utils.policy_formatters import serialize_policy

logger = logging.getLogger(__name__)

_DEFAULT_ORDER_INDEX = 999


class IntegrationService:
    """Импорт структуры курса и правил из СДО, чтение метаданных онтологии."""

    def __init__(
        self,
        core: OntologyCore,
        *,
        verification: VerificationService,
        cache: CacheManager,
    ) -> None:
        self.core = core
        self.verification = verification
        self.cache = cache

    def get_meta(self) -> dict:
        rule_types = [rt.value for rt in RuleType]
        statuses = [ps.value for ps in ProgressStatus]

        competencies: List[dict] = []
        for comp in self.core.courses.get_all_competencies():
            parent_list = getattr(comp, "is_subcompetency_of", [])
            parent_id = parent_list[0].name if parent_list else None
            competencies.append({
                "id": comp.name,
                "name": label_or_name(comp),
                "parent_id": parent_id,
            })

        course_elements: List[dict] = []
        for el in self.core.courses.get_all_elements():
            raw_type = el.type[0] if getattr(el, "type", None) else None
            if not raw_type:
                raw_type = el.__class__.__name__.lower()
            course_elements.append({
                "id": el.name,
                "name": label_or_name(el),
                "type": raw_type,
                "is_mandatory": get_owl_prop(el, "is_mandatory", True),
            })

        groups: List[dict] = []
        group_cls = getattr(self.core.onto, "Group", None)
        if group_cls is not None:
            for grp in group_cls.instances():
                # для UI отдаём только прямого родителя; транзитивное замыкание не разворачиваем
                parents = list(getattr(grp, "is_subgroup_of", []) or [])
                parent_id = parents[0].name if parents else None
                groups.append({
                    "id": grp.name,
                    "name": label_or_name(grp),
                    "parent_id": parent_id,
                })

        return {
            "rule_types": rule_types,
            "statuses": statuses,
            "competencies": competencies,
            "course_elements": course_elements,
            "groups": groups,
        }

    def sync_course_structure(
        self,
        course_id: str,
        payload: CourseSyncPayload,
        run_verification: bool = True,
    ) -> dict:
        course_class = ELEMENT_TYPE_TO_OWL_CLASS[ElementType.COURSE.value]
        course = self.core.courses.get_or_create_element(course_id, course_class)
        course.label = [payload.course_name]
        course.is_mandatory = True

        # soft reset: разрываем связи, сами индивиды оставляем — на них могут висеть политики
        for old_module in list(course.has_module):
            old_module.contains_activity = []
        course.has_module = []

        for idx, elem_data in enumerate(payload.elements):
            element_type = str(elem_data.element_type).lower()
            class_name = ELEMENT_TYPE_TO_OWL_CLASS.get(element_type, COURSE_STRUCTURE_OWL_CLASS)
            element = self.core.courses.get_or_create_element(elem_data.element_id, class_name)

            element.label = [elem_data.name]
            element.type = [element_type]
            element.is_mandatory = getattr(elem_data, "is_mandatory", True)

            final_order = elem_data.order_index if getattr(elem_data, "order_index", None) is not None else idx
            element.order_index = final_order

            if elem_data.parent_id:
                parent = self.core.courses.find_by_id(elem_data.parent_id)
                if not parent:
                    parent = self.core.courses.get_or_create_element(elem_data.parent_id, COURSE_STRUCTURE_OWL_CLASS)

                if element_type == ElementType.MODULE.value:
                    if element not in getattr(parent, "has_module", []):
                        parent.has_module.append(element)
                else:
                    if element not in getattr(parent, "contains_activity", []):
                        parent.contains_activity.append(element)

        self.core.save()
        self.cache.invalidate_verification(course.name)

        result = {
            "status": "success",
            "course_id": course.name,
            "synced_elements_count": len(payload.elements),
        }

        if run_verification:
            try:
                report = self.verification.verify(course.name, use_cache=False)
                result["verification_summary"] = report.to_dict().get("summary")
            except Exception as exc:
                logger.warning("Автоверификация после sync упала: %s", exc)
                result["verification_summary"] = f"verification_failed: {exc}"

        return result

    def get_course_tree(self, course_id: str) -> List[dict]:
        course = self.core.courses.find_by_id(course_id)
        if not course:
            return []

        def build_node(node_obj, node_type_override=None):
            node_id = node_obj.name
            raw_type = node_type_override or node_obj.__class__.__name__.lower()

            policies = [
                serialize_policy(pol, source_id=node_id)
                for pol in getattr(node_obj, "has_access_policy", []) or []
            ]

            if raw_type == ElementType.COURSE.value:
                children_objs = getattr(node_obj, "has_module", [])
            elif raw_type == ElementType.MODULE.value:
                children_objs = getattr(node_obj, "contains_activity", [])
            else:
                children_objs = []

            children_objs = sorted(
                children_objs,
                key=lambda x: get_owl_prop(x, "order_index", _DEFAULT_ORDER_INDEX),
            )

            children = [build_node(child) for child in children_objs]

            assesses_items = [
                {"id": comp.name, "name": label_or_name(comp)}
                for comp in getattr(node_obj, "assesses", []) or []
            ]

            return {
                "key": node_id,
                "data": {
                    "id": node_id,
                    "name": label_or_name(node_obj) or node_id,
                    "type": get_owl_prop(node_obj, "type", raw_type),
                    "policies": policies,
                    "is_mandatory": get_owl_prop(node_obj, "is_mandatory", True),
                    "assesses": assesses_items,
                },
                "children": children,
            }

        return [build_node(course, ElementType.COURSE.value)]

    def set_element_competencies(self, element_id: str, competency_ids: List[str]) -> dict:
        element = self.core.courses.find_by_id(element_id)
        if element is None:
            raise ValueError(f"Элемент {element_id} не найден.")

        comp_cls = getattr(self.core.onto, "Competency", None)
        if comp_cls is None:
            raise ValueError("В онтологии нет класса Competency.")

        competencies: List[Any] = []
        for cid in competency_ids:
            comp = self.core.onto.search_one(type=comp_cls, iri=f"*{cid}")
            if comp is None:
                raise ValueError(f"Компетенция {cid} не найдена.")
            competencies.append(comp)

        element.assesses = competencies
        self.core.save()
        # OWL монотонен — без сброса кэша has_competency не пересчитается;
        # сам резонер дёрнет AccessService при первом чтении
        self.cache.invalidate_all_access()
        self.cache.invalidate_verification()
        return {
            "element_id": element_id,
            "assesses": [{"id": c.name, "name": label_or_name(c)} for c in competencies],
        }

    def set_element_mandatory(self, element_id: str, is_mandatory: bool) -> dict:
        element = self.core.courses.find_by_id(element_id)
        if element is None:
            raise ValueError(f"Элемент {element_id} не найден.")

        flag = bool(is_mandatory)
        element.is_mandatory = flag
        self.core.save()
        self.cache.invalidate_all_access()
        self.cache.invalidate_verification()
        return {"element_id": element_id, "is_mandatory": flag}
