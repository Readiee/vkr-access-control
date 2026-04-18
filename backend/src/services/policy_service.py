import uuid
from typing import List, Optional, Any
from schemas.schemas import PolicyCreate
from services.graph_validator import GraphValidator
from services.ontology_core import OntologyCore
from core.enums import RuleType

class PolicyService:
    """Сервис управления политиками доступа в онтологии."""

    def __init__(self, core: OntologyCore) -> None:
        self.core = core

    def _invalidate_all_access_caches(self):
        """Сбрасывает кэш доступов для всех студентов при изменении политик."""
        self.core.cache.invalidate_all_access()

    def _map_policy_to_dict(self, policy_node: Any, source_id: str) -> dict:
        """Сериализует OWL-индивид AccessPolicy в словарь."""
        return {
            "id": policy_node.name,
            "source_element_id": source_id,
            "rule_type": policy_node.rule_type[0] if policy_node.rule_type else "",
            "target_element_id": (
                policy_node.targets_element[0].name if getattr(policy_node, "targets_element", None) else None
            ),
            "target_competency_id": (
                policy_node.targets_competency[0].name if getattr(policy_node, "targets_competency", None) else None
            ),
            "passing_threshold": (
                policy_node.passing_threshold[0]
                if getattr(policy_node, "passing_threshold", None)
                else None
            ),
            "available_from": (
                policy_node.available_from[0]
                if getattr(policy_node, "available_from", None)
                else None
            ),
            "available_until": (
                policy_node.available_until[0]
                if getattr(policy_node, "available_until", None)
                else None
            ),
            "is_active": policy_node.is_active[0] if getattr(policy_node, "is_active", None) else False,
            "author_id": policy_node.has_author[0].name if getattr(policy_node, "has_author", None) else "system",
        }

    def create_policy(self, policy_data: PolicyCreate) -> dict:
        """Создаёт индивид AccessPolicy в графе и сохраняет онтологию."""
        if policy_data.target_element_id:
            if policy_data.source_element_id == policy_data.target_element_id:
                raise ValueError("Элемент не может требовать прохождения себя (самореференция).")
            cycle_path = GraphValidator.check_for_cycles(self.core.onto, policy_data.source_element_id, policy_data.target_element_id)
            if cycle_path:
                readable = [self.core._get_node_label(nid) for nid in cycle_path]
                raise ValueError(f"Циклическая зависимость: {' -> '.join(readable)}")

        policy_id = f"policy_{uuid.uuid4().hex[:8]}"
        new_policy = self.core.policies.create_or_update(policy_id)

        new_policy.rule_type = [policy_data.rule_type]
        new_policy.is_active = [getattr(policy_data, 'is_active', True)]

        if policy_data.passing_threshold is not None:
            new_policy.passing_threshold = [policy_data.passing_threshold]
        if policy_data.available_from:
            new_policy.available_from = [policy_data.available_from]
        if policy_data.available_until:
            new_policy.available_until = [policy_data.available_until]

        author = self.core._get_or_create_element(policy_data.author_id, self.core.onto.Methodologist)
        new_policy.has_author = [author]

        if policy_data.target_element_id:
            target = self.core.courses.find_by_id(policy_data.target_element_id)
            if not target:
                target = self.core.courses.get_or_create_element(policy_data.target_element_id, "CourseStructure")
            new_policy.targets_element = [target]

        if policy_data.target_competency_id:
            comp = self.core.courses.find_by_id(policy_data.target_competency_id)
            if comp:
                new_policy.targets_competency = [comp]

        source = self.core.courses.find_by_id(policy_data.source_element_id)
        if not source:
            source = self.core.courses.get_or_create_element(policy_data.source_element_id, "CourseStructure")
        source.has_access_policy.append(new_policy)

        self.core.save()
        self.core.run_reasoner()
        self._invalidate_all_access_caches()
        return self._map_policy_to_dict(new_policy, policy_data.source_element_id)

    def get_policies(
        self,
        course_id: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> List[dict]:
        """Возвращает список политик с опциональной фильтрацией по элементу."""
        policies: List[dict] = []
        # Мы все еще можем использовать instances() через repo если добавим метод, или напрямую через onto если разрешено
        for policy in self.core.onto.AccessPolicy.instances():
            source_elements = self.core.policies.find_by_source_element(policy)
            source_id: str = source_elements[0].name if source_elements else "unknown"

            if element_id and source_id != element_id:
                continue

            policies.append(self._map_policy_to_dict(policy, source_id))
        return policies

    def delete_policy(self, policy_id: str) -> bool:
        """Безопасно удаляет AccessPolicy, отсоединяя её от всех источников."""
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            return False
        source_elements = self.core.policies.find_by_source_element(policy)
        for element in source_elements:
            if policy in element.has_access_policy:
                element.has_access_policy.remove(policy)
        self.core.policies.delete(policy)
        self.core.save()
        self.core.run_reasoner()
        self._invalidate_all_access_caches()
        return True

    def update_policy(self, policy_id: str, data: PolicyCreate) -> dict:
        """Обновляет существующую AccessPolicy новыми данными."""
        if data.target_element_id:
            if data.source_element_id == data.target_element_id:
                raise ValueError("Элемент не может требовать прохождения себя (самореференция).")
            cycle_path = GraphValidator.check_for_cycles(self.core.onto, data.source_element_id, data.target_element_id)
            if cycle_path:
                readable = [self.core._get_node_label(nid) for nid in cycle_path]
                raise ValueError(f"Циклическая зависимость: {' -> '.join(readable)}")

        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            raise ValueError(f"Политика с ID {policy_id} не найдена")

        new_type = data.rule_type
        policy.rule_type = [new_type]
        policy.is_active = [getattr(data, 'is_active', True)]
        
        # Очистка мусора при смене типа
        if new_type in [RuleType.COMPLETION.value, RuleType.VIEWED.value]:
            policy.passing_threshold = []
            policy.targets_competency = []
            if data.target_element_id:
                target_el = self.core.courses.find_by_id(data.target_element_id)
                policy.targets_element = [target_el] if target_el else []
            else:
                policy.targets_element = []
        elif new_type == RuleType.GRADE.value:
            policy.targets_competency = []
            policy.passing_threshold = [data.passing_threshold] if data.passing_threshold is not None else []
            if data.target_element_id:
                target_el = self.core.courses.find_by_id(data.target_element_id)
                policy.targets_element = [target_el] if target_el else []
            else:
                policy.targets_element = []
        elif new_type == RuleType.COMPETENCY.value:
            policy.passing_threshold = []
            policy.targets_element = []
            if data.target_competency_id:
                target_comp = self.core.courses.find_by_id(data.target_competency_id)
                policy.targets_competency = [target_comp] if target_comp else []
            else:
                policy.targets_competency = []
        elif new_type == RuleType.DATE.value:
            policy.passing_threshold = []
            policy.targets_element = []
            policy.targets_competency = []
            
        policy.available_from = [data.available_from] if data.available_from else []
        policy.available_until = [data.available_until] if data.available_until else []

        self.core.save()
        self.core.run_reasoner()
        self._invalidate_all_access_caches()

        source_elements = self.core.policies.find_by_source_element(policy)
        source_id = source_elements[0].name if source_elements else data.source_element_id
        return self._map_policy_to_dict(policy, source_id)

    def toggle_policy(self, policy_id: str, is_active: bool) -> None:
        """Переключает флаг is_active для политики."""
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            raise ValueError(f"Политика с ID {policy_id} не найдена")
        policy.is_active = [is_active]
        self.core.save()
        self.core.run_reasoner()
        self._invalidate_all_access_caches()
