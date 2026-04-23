import logging
import uuid
from typing import Any, List, Optional

from owlready2 import AllDifferent

from core.enums import RuleType
from schemas.schemas import PolicyCreate
from services.cache_manager import CacheManager
from services.graph_validator import GraphValidator, ProbePolicy
from services.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator

logger = logging.getLogger(__name__)


class PolicyConflictError(Exception):
    """Политика создаёт логическое противоречие с остальной онтологией."""

    def __init__(self, explanation: str):
        super().__init__(explanation)
        self.explanation = explanation


class PolicyService:
    """Сервис управления политиками доступа в онтологии.

    По DSL §35, §97–§100: зависит от OntologyCore (мутация TBox/ABox),
    GraphValidator (проверка ацикличности), ReasoningOrchestrator (проверка
    консистентности) и CacheManager (инвалидация затронутых ключей).
    """

    def __init__(
        self,
        core: OntologyCore,
        *,
        reasoner: ReasoningOrchestrator,
        cache: CacheManager,
    ) -> None:
        self.core = core
        self.reasoner = reasoner
        self.cache = cache

    def _invalidate_all_access_caches(self) -> None:
        self.cache.invalidate_all_access()
        self.cache.invalidate_verification()

    def _rule_type_str(self, value: Any) -> str:
        return value if isinstance(value, str) else value.value

    def _map_policy_to_dict(self, policy_node: Any, source_id: str) -> dict:
        return {
            "id": policy_node.name,
            "source_element_id": source_id,
            "rule_type": policy_node.rule_type[0] if policy_node.rule_type else "",
            "target_element_id": (
                policy_node.targets_element[0].name
                if getattr(policy_node, "targets_element", None)
                else None
            ),
            "target_competency_id": (
                policy_node.targets_competency[0].name
                if getattr(policy_node, "targets_competency", None)
                else None
            ),
            "passing_threshold": (
                policy_node.passing_threshold[0]
                if getattr(policy_node, "passing_threshold", None)
                else None
            ),
            "valid_from": (
                policy_node.valid_from[0]
                if getattr(policy_node, "valid_from", None)
                else None
            ),
            "valid_until": (
                policy_node.valid_until[0]
                if getattr(policy_node, "valid_until", None)
                else None
            ),
            "restricted_to_group_id": (
                policy_node.restricted_to_group[0].name
                if getattr(policy_node, "restricted_to_group", None)
                else None
            ),
            "subpolicy_ids": [sub.name for sub in getattr(policy_node, "has_subpolicy", []) or []] or None,
            "aggregate_function": getattr(policy_node, "aggregate_function", None),
            "aggregate_element_ids": (
                [e.name for e in getattr(policy_node, "aggregate_elements", []) or []] or None
            ),
            "is_active": policy_node.is_active[0] if getattr(policy_node, "is_active", None) else False,
            "author_id": policy_node.has_author[0].name if getattr(policy_node, "has_author", None) else "system",
        }

    def _build_probe(self, policy_data: PolicyCreate) -> ProbePolicy:
        rule_type = self._rule_type_str(policy_data.rule_type)
        return ProbePolicy(
            rule_type=rule_type,
            source_id=policy_data.source_element_id,
            target_element_id=policy_data.target_element_id,
            target_competency_id=policy_data.target_competency_id,
            subpolicy_ids=list(policy_data.subpolicy_ids or []),
            aggregate_element_ids=list(policy_data.aggregate_element_ids or []),
        )

    def _check_cycle(self, policy_data: PolicyCreate) -> None:
        # Политика без source — только подполитика композита, в граф зависимостей
        # не попадает (не висит через has_access_policy).
        if not policy_data.source_element_id:
            return
        rule_type = self._rule_type_str(policy_data.rule_type)
        if rule_type in {RuleType.DATE.value, RuleType.GROUP.value}:
            return
        if (
            rule_type in {RuleType.COMPLETION.value, RuleType.GRADE.value, RuleType.VIEWED.value}
            and policy_data.target_element_id
            and policy_data.source_element_id == policy_data.target_element_id
        ):
            raise ValueError("Элемент не может требовать прохождения себя (самореференция).")
        if rule_type == RuleType.AGGREGATE.value and policy_data.aggregate_element_ids:
            if policy_data.source_element_id in policy_data.aggregate_element_ids:
                raise ValueError("Элемент не может агрегировать сам себя.")
        probe = self._build_probe(policy_data)
        cycle_path = GraphValidator.check_for_cycles(self.core.onto, probe.source_id, probe=probe)
        if cycle_path:
            readable = [self.core._get_node_label(nid) for nid in cycle_path]
            raise ValueError(f"Циклическая зависимость: {' -> '.join(readable)}")

    def create_policy(self, policy_data: PolicyCreate) -> dict:
        """Создать AccessPolicy в графе и сохранить онтологию.

        Поддержка nested_subpolicies: если в payload приложены свежесозданные
        подусловия — они создаются рекурсивно в том же порядке, их id добавляются
        к subpolicy_ids родителя.
        """
        nested = list(getattr(policy_data, "nested_subpolicies", None) or [])
        created_children: List[Any] = []
        if nested:
            for child in nested:
                child_copy = child.model_copy(update={
                    "source_element_id": None,
                    "is_active": True,
                    "nested_subpolicies": None,
                })
                child_dict = self.create_policy(child_copy)
                created_children.append(child_dict["id"])
            merged_ids = list(policy_data.subpolicy_ids or []) + created_children
            policy_data = policy_data.model_copy(update={
                "subpolicy_ids": merged_ids,
                "nested_subpolicies": None,
            })

        self._check_cycle(policy_data)

        policy_id = f"policy_{uuid.uuid4().hex[:8]}"
        new_policy = self.core.policies.create_or_update(policy_id)

        rule_type_value = self._rule_type_str(policy_data.rule_type)
        new_policy.rule_type = [rule_type_value]
        new_policy.is_active = [getattr(policy_data, 'is_active', True)]

        self._apply_type_specific_fields(new_policy, policy_data, rule_type_value)

        author = self.core._get_or_create_element(policy_data.author_id, self.core.onto.Methodologist)
        new_policy.has_author = [author]

        source = None
        if policy_data.source_element_id:
            source = self.core.courses.find_by_id(policy_data.source_element_id)
            if not source:
                source = self.core.courses.get_or_create_element(
                    policy_data.source_element_id, "CourseStructure"
                )
            source.has_access_policy.append(new_policy)

        result = self.reasoner.reason()
        if result.status == "inconsistent":
            logger.warning("Политика %s сделала онтологию inconsistent: %s", policy_id, result.error)
            self._rollback_policy(new_policy, source)
            raise PolicyConflictError(
                f"Политика создаёт логическое противоречие: {result.error or 'онтология inconsistent'}"
            )
        if result.status == "error":
            self._rollback_policy(new_policy, source)
            raise PolicyConflictError(f"Ошибка reasoning: {result.error}")

        self.core.save()
        self._invalidate_all_access_caches()
        return self._map_policy_to_dict(new_policy, policy_data.source_element_id)

    def _apply_type_specific_fields(
        self,
        policy: Any,
        data: PolicyCreate,
        rule_type: str,
    ) -> None:
        """Перенести поля PolicyCreate в ABox в зависимости от rule_type."""
        if data.passing_threshold is not None:
            policy.passing_threshold = [data.passing_threshold]
        if data.valid_from:
            policy.valid_from = [data.valid_from]
        if data.valid_until:
            policy.valid_until = [data.valid_until]

        if data.target_element_id:
            target = self.core.courses.find_by_id(data.target_element_id)
            if not target:
                target = self.core.courses.get_or_create_element(data.target_element_id, "CourseStructure")
            policy.targets_element = [target]

        if data.target_competency_id:
            comp = self.core.courses.find_by_id(data.target_competency_id)
            if comp:
                policy.targets_competency = [comp]

        if rule_type == RuleType.GROUP.value and data.restricted_to_group_id:
            group = self.core.onto.search_one(
                type=self.core.onto.Group, iri=f"*{data.restricted_to_group_id}"
            )
            if group is None:
                raise ValueError(f"Группа {data.restricted_to_group_id} не найдена.")
            policy.restricted_to_group = [group]

        if rule_type in {RuleType.AND.value, RuleType.OR.value} and data.subpolicy_ids:
            subs: List[Any] = []
            for sub_id in data.subpolicy_ids:
                sub = self.core.policies.find_by_id(sub_id)
                if sub is None:
                    raise ValueError(f"Подполитика {sub_id} не найдена.")
                subs.append(sub)
            policy.has_subpolicy = subs
            # Unique Name Assumption выключен в OWL (OWA); SWRL DifferentFrom
            # срабатывает только при явной декларации AllDifferent.
            if rule_type == RuleType.AND.value and len(subs) >= 2:
                AllDifferent(subs)

        if rule_type == RuleType.AGGREGATE.value:
            fn = data.aggregate_function.value if hasattr(data.aggregate_function, "value") else data.aggregate_function
            policy.aggregate_function = fn
            agg_elements: List[Any] = []
            for eid in data.aggregate_element_ids or []:
                elem = self.core.courses.find_by_id(eid)
                if elem is None:
                    raise ValueError(f"Элемент агрегата {eid} не найден.")
                agg_elements.append(elem)
            policy.aggregate_elements = agg_elements

    def _rollback_policy(self, policy_node: Any, source_node: Any) -> None:
        """Снять политику с элемента и удалить её из ABox."""
        try:
            if policy_node in source_node.has_access_policy:
                source_node.has_access_policy.remove(policy_node)
            self.core.policies.delete(policy_node)
        except Exception:
            logger.exception("Откат политики %s не удался", getattr(policy_node, "name", "?"))

    def get_policies(
        self,
        course_id: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> List[dict]:
        """Список политик с опциональной фильтрацией по элементу."""
        policies: List[dict] = []
        for policy in self.core.onto.AccessPolicy.instances():
            source_elements = self.core.policies.find_by_source_element(policy)
            source_id: str = source_elements[0].name if source_elements else "unknown"
            if element_id and source_id != element_id:
                continue
            policies.append(self._map_policy_to_dict(policy, source_id))
        return policies

    def delete_policy(self, policy_id: str) -> bool:
        """Удалить AccessPolicy, отсоединив от всех источников."""
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            return False
        source_elements = self.core.policies.find_by_source_element(policy)
        for element in source_elements:
            if policy in element.has_access_policy:
                element.has_access_policy.remove(policy)
        self.core.policies.delete(policy)
        self.core.save()
        self.reasoner.reason()
        self._invalidate_all_access_caches()
        return True

    def update_policy(self, policy_id: str, data: PolicyCreate) -> dict:
        """Обновить существующую AccessPolicy новыми данными.

        Для AND/OR поддерживается nested_subpolicies: старые подусловия, которые
        использовались только этим композитом, удаляются из ABox; новые
        создаются атомарно и подвязываются как has_subpolicy.
        """
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            raise ValueError(f"Политика с ID {policy_id} не найдена")

        old_subs = list(getattr(policy, "has_subpolicy", []) or [])

        nested = list(getattr(data, "nested_subpolicies", None) or [])
        if nested:
            created_ids: List[str] = []
            for child in nested:
                child_copy = child.model_copy(update={
                    "source_element_id": None,
                    "is_active": True,
                    "nested_subpolicies": None,
                })
                child_dict = self.create_policy(child_copy)
                created_ids.append(child_dict["id"])
            merged = list(data.subpolicy_ids or []) + created_ids
            data = data.model_copy(update={
                "subpolicy_ids": merged,
                "nested_subpolicies": None,
            })

        self._check_cycle(data)

        new_type = self._rule_type_str(data.rule_type)
        policy.rule_type = [new_type]
        policy.is_active = [getattr(data, 'is_active', True)]
        policy.passing_threshold = []
        policy.targets_element = []
        policy.targets_competency = []
        policy.valid_from = []
        policy.valid_until = []
        policy.restricted_to_group = []
        policy.has_subpolicy = []
        policy.aggregate_elements = []
        policy.aggregate_function = None

        self._apply_type_specific_fields(policy, data, new_type)

        self._cleanup_orphan_nested(policy, old_subs)

        self.core.save()
        self.reasoner.reason()
        self._invalidate_all_access_caches()

        source_elements = self.core.policies.find_by_source_element(policy)
        source_id = source_elements[0].name if source_elements else data.source_element_id
        return self._map_policy_to_dict(policy, source_id)

    def _cleanup_orphan_nested(self, parent_policy: Any, old_subs: List[Any]) -> None:
        """Удаляет подусловия, которые были вложены только в parent_policy и не
        висят ни на одном элементе как самостоятельная политика.

        Безопасно оставляет subpolicy, если:
        - она продолжает использоваться этим же composite (не «старая» после update),
        - её же ссылается другой composite,
        - у неё есть source-элемент (значит, это отдельная политика).
        """
        current_subs = set(getattr(parent_policy, "has_subpolicy", []) or [])
        all_elements = self.core.courses.get_all_elements()
        all_policies = list(self.core.onto.AccessPolicy.instances())
        for old in old_subs:
            if old in current_subs:
                continue
            has_source = any(old in getattr(el, "has_access_policy", []) for el in all_elements)
            if has_source:
                continue
            used_elsewhere = any(
                old in getattr(p, "has_subpolicy", []) for p in all_policies if p is not parent_policy
            )
            if used_elsewhere:
                continue
            self.core.policies.delete(old)

    def toggle_policy(self, policy_id: str, is_active: bool) -> None:
        """Переключить флаг is_active."""
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            raise ValueError(f"Политика с ID {policy_id} не найдена")
        policy.is_active = [is_active]
        self.core.save()
        self.reasoner.reason()
        self._invalidate_all_access_caches()
