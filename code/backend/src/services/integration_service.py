import logging
from typing import Any, Dict, List, Optional

from core.enums import ElementType, ProgressStatus, RuleType
from schemas.schemas import CourseElement, CourseSyncPayload
from services.cache_manager import CacheManager
from services.ontology_core import OntologyCore
from services.verification import VerificationService
from utils.owl_utils import get_owl_prop
from utils.policy_formatters import serialize_policy

logger = logging.getLogger(__name__)


class IntegrationService:
    """Импорт структуры курса и правил из СДО + чтение метаданных онтологии.

    По DSL §94, §116–§118: IntegrationController делегирует сюда; после импорта
    структуры запускается автоверификация через VerificationService (решение
    18.04, UC-10 → UC-6). Чтение дерева и meta-endpoints — утилитная часть,
    нужна фронту.
    """

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
            course_elements.append({
                "id": el.name,
                "name": el.label[0] if getattr(el, "label", None) else el.name,
                "type": raw_type,
                "is_mandatory": get_owl_prop(el, "is_mandatory", True),
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

    def sync_course_structure(
        self,
        course_id: str,
        payload: CourseSyncPayload,
        run_verification: bool = True,
    ) -> dict:
        course = self.core.courses.get_or_create_element(course_id, "Course")
        course.label = [payload.course_name]
        course.is_mandatory = True
        
        # Soft Reset курса (удаление только связей)
        for old_module in list(course.has_module):
            old_module.contains_activity = []
        course.has_module = []

        # Сборка иерархии по новому payload

        for idx, elem_data in enumerate(payload.elements):
            class_name = elem_data.element_type.capitalize()
            element = self.core.courses.get_or_create_element(elem_data.element_id, class_name)
            
            element.label = [elem_data.name]
            element.type = [elem_data.element_type.lower()]
            element.is_mandatory = getattr(elem_data, "is_mandatory", True)
            
            # Неявная или явная сортировка
            final_order = elem_data.order_index if getattr(elem_data, "order_index", None) is not None else idx
            element.order_index = final_order

            if elem_data.parent_id:
                parent = self.core.courses.find_by_id(elem_data.parent_id)
                if not parent:
                    parent = self.core.courses.get_or_create_element(elem_data.parent_id, "CourseStructure")

                if elem_data.element_type == ElementType.MODULE.value:
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

        # Автоверификация (DSL §118, решение 18.04): после импорта сразу прогоняем
        # UC-6. На успехе — сводка; на ошибке — импорт оставляем, а верификация
        # помечается как failed. Флаг run_verification позволяет отключить
        # автоверификацию в smoke-тестах симулятора, где создание курса —
        # чисто setup-шаг без проверок.
        if run_verification:
            try:
                report = self.verification.verify(course.name, use_cache=False)
                result["verification_summary"] = report.to_dict().get("summary")
            except Exception as exc:
                logger.warning("Автоверификация после sync упала: %s", exc)
                result["verification_summary"] = f"verification_failed: {exc}"

        return result

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
                policies.append(serialize_policy(pol, source_id=node_id))

            if raw_type == ElementType.COURSE.value:
                children_objs = getattr(node_obj, "has_module", [])
            elif raw_type == ElementType.MODULE.value:
                children_objs = getattr(node_obj, "contains_activity", [])
            else:
                children_objs = []

            children_objs = sorted(
                children_objs,
                key=lambda x: get_owl_prop(x, "order_index", 999)  # элементы без индекса уходят в конец
            )

            children = [build_node(child) for child in children_objs]

            assesses_items = []
            for comp in getattr(node_obj, "assesses", []) or []:
                comp_name = comp.label[0] if getattr(comp, "label", None) else comp.name
                assesses_items.append({"id": comp.name, "name": comp_name})

            return {
                "key": node_id,
                "data": {
                    "id": node_id,
                    "name": node_name,
                    "type": get_owl_prop(node_obj, "type", raw_type),
                    "policies": policies,
                    "is_mandatory": get_owl_prop(node_obj, "is_mandatory", True),
                    "assesses": assesses_items,
                },
                "children": children
            }

        return [build_node(course, ElementType.COURSE.value)]

    def set_element_competencies(self, element_id: str, competency_ids: List[str]) -> dict:
        """Перезаписать assesses у элемента: список компетенций, которые он выдаёт
        студенту при прохождении (SWRL H-2). Инвалидирует кэш доступа и верификации
        и гоняет reasoner — без этого has_competency у уже существующих ProgressRecord
        не обновится (OWL монотонен).
        """
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
        # После изменения assesses SWRL H-2 может изменить has_competency у всех
        # студентов с ProgressRecord этого элемента → is_available_for тоже.
        # Инвалидируем access-кэш и запускаем reasoner через verification-путь
        # не будем (он дорогой); AccessService пересчитает лениво на первом чтении.
        self.cache.invalidate_all_access()
        self.cache.invalidate_verification()
        return {
            "element_id": element_id,
            "assesses": [{"id": c.name, "name": (c.label[0] if getattr(c, "label", None) else c.name)} for c in competencies],
        }

    def set_element_mandatory(self, element_id: str, is_mandatory: bool) -> dict:
        """Перезаписать флаг обязательности элемента.

        Влияет на Roll-up: модуль/курс считается завершённым только если все
        обязательные потомки завершены. Смена флага инвалидирует access-кэш;
        Roll-up пересчитается при следующем simulate_progress.
        """
        element = self.core.courses.find_by_id(element_id)
        if element is None:
            raise ValueError(f"Элемент {element_id} не найден.")

        # is_mandatory — FunctionalProperty, scalar API
        element.is_mandatory = bool(is_mandatory)
        self.core.save()
        self.cache.invalidate_all_access()
        self.cache.invalidate_verification()
        return {"element_id": element_id, "is_mandatory": bool(is_mandatory)}
