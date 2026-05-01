import logging
import uuid
from typing import Any, List, Optional

from core.enums import (
    COMPOSITE_RULE_TYPES,
    COURSE_STRUCTURE_OWL_CLASS,
    ReasoningStatus,
    RuleType,
)
from schemas import PolicyCreate
from core.cache_manager import CacheManager
from services.verification.graph_validator import GraphValidator, ProbePolicy
from core.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator
from services.rule_handlers import REGISTRY
from utils.owl_utils import get_owl_prop
from utils.policy_formatters import serialize_policy

logger = logging.getLogger(__name__)


class PolicyConflictError(Exception):
    """Политика создаёт логическое противоречие с остальной онтологией."""

    def __init__(self, explanation: str):
        super().__init__(explanation)
        self.explanation = explanation


class PolicyNotFoundError(LookupError):
    def __init__(self, policy_id: str):
        super().__init__(policy_id)
        self.policy_id = policy_id


_SNAPSHOT_SCALAR_PROPS = (
    "rule_type",
    "is_active",
    "passing_threshold",
    "targets_element",
    "valid_from",
    "valid_until",
    "restricted_to_group",
    "aggregate_function",
)
_SNAPSHOT_LIST_PROPS = (
    "targets_competency",
    "has_subpolicy",
    "aggregate_elements",
)
_RESET_EXCLUDED = frozenset({"rule_type", "is_active"})


def _is_composite(rule_type: str) -> bool:
    return rule_type in COMPOSITE_RULE_TYPES


class PolicyService:
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

    def create_policy(self, policy_data: PolicyCreate) -> dict:
        policy_data, created_children = self._materialize_nested(policy_data)

        try:
            self._check_cycle(policy_data)
        except Exception:
            self._delete_policies_by_id(created_children)
            raise

        policy_id = f"policy_{uuid.uuid4().hex[:8]}"
        new_policy = self.core.policies.create_or_update(policy_id)

        rule_type_value = self._rule_type_str(policy_data.rule_type)
        new_policy.rule_type = rule_type_value
        new_policy.is_active = self._effective_is_active(rule_type_value, policy_data)
        self._apply_type_specific_fields(new_policy, policy_data, rule_type_value)

        author = self.core._get_or_create_element(policy_data.author_id, self.core.onto.Methodologist)
        new_policy.has_author = author

        source = self._attach_to_source(new_policy, policy_data.source_element_id)

        result = self.reasoner.reason()
        if result.status != ReasoningStatus.OK.value:
            self._rollback_policy(new_policy, source)
            self._delete_policies_by_id(created_children)
            if result.status == ReasoningStatus.INCONSISTENT.value:
                logger.warning("Политика %s сделала онтологию inconsistent: %s", policy_id, result.error)
                raise PolicyConflictError(
                    f"Политика создаёт логическое противоречие: {result.error or 'онтология inconsistent'}"
                )
            raise PolicyConflictError(f"Reasoning {result.status}: {result.error or '—'}")

        self.core.save()
        self._invalidate_caches()
        return serialize_policy(new_policy, source_id=policy_data.source_element_id)

    def get_policies(
        self,
        course_id: Optional[str] = None,
        element_id: Optional[str] = None,
    ) -> List[dict]:
        course_scope = self.core.courses.subtree_ids(course_id) if course_id else None
        policies: List[dict] = []
        for policy in self.core.onto.AccessPolicy.instances():
            source_elements = self.core.policies.find_by_source_element(policy)
            source_id: str = source_elements[0].name if source_elements else "unknown"
            if element_id and source_id != element_id:
                continue
            if course_scope is not None and source_id not in course_scope:
                continue
            policies.append(serialize_policy(policy, source_id=source_id))
        return policies

    def delete_policy(self, policy_id: str) -> bool:
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            return False
        source_elements = self.core.policies.find_by_source_element(policy)
        for element in source_elements:
            if policy in element.has_access_policy:
                element.has_access_policy.remove(policy)
        self.core.policies.delete(policy)
        result = self.reasoner.reason()
        if result.status != ReasoningStatus.OK.value:
            # на диск пишем только консистентное состояние; без save следующий запуск
            # снова увидит политику, хотя в памяти она уже снята
            logger.warning(
                "Резонер после delete_policy %s вернул %s: %s",
                policy_id, result.status, result.error,
            )
            self._invalidate_caches()
            raise PolicyConflictError(
                f"После удаления политики reasoning {result.status}: {result.error or '—'}"
            )
        self.core.save()
        self._invalidate_caches()
        return True

    def update_policy(self, policy_id: str, data: PolicyCreate) -> dict:
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            raise PolicyNotFoundError(policy_id)

        snapshot = self._snapshot_policy(policy)
        old_subs = list(getattr(policy, "has_subpolicy", []) or [])

        data, created_nested = self._materialize_nested(data)

        try:
            self._check_cycle(data)
        except Exception:
            self._delete_policies_by_id(created_nested)
            raise

        new_type = self._rule_type_str(data.rule_type)
        policy.rule_type = new_type
        policy.is_active = self._effective_is_active(new_type, data)
        self._reset_policy_fields(policy)

        self._apply_type_specific_fields(policy, data, new_type)

        result = self.reasoner.reason()
        if result.status != ReasoningStatus.OK.value:
            self._restore_policy(policy, snapshot)
            self._delete_policies_by_id(created_nested)
            if result.status == ReasoningStatus.INCONSISTENT.value:
                raise PolicyConflictError(
                    f"Политика создаёт логическое противоречие: {result.error or 'онтология inconsistent'}"
                )
            raise PolicyConflictError(f"Reasoning {result.status}: {result.error or '—'}")

        # cleanup только после успешного reason: rollback по snapshot ссылается на
        # старые has_subpolicy и поломается, если их уже уничтожили
        self._cleanup_orphan_nested(policy, old_subs)

        self.core.save()
        self._invalidate_caches()

        source_elements = self.core.policies.find_by_source_element(policy)
        source_id = source_elements[0].name if source_elements else data.source_element_id
        return serialize_policy(policy, source_id=source_id)

    def toggle_policy(self, policy_id: str, is_active: bool) -> None:
        policy = self.core.policies.find_by_id(policy_id)
        if not policy:
            raise PolicyNotFoundError(policy_id)
        previous = bool(get_owl_prop(policy, "is_active", True))
        policy.is_active = bool(is_active)
        result = self.reasoner.reason()
        if result.status != ReasoningStatus.OK.value:
            policy.is_active = previous
            self._invalidate_caches()
            raise PolicyConflictError(
                f"Переключение активности привело к reasoning {result.status}: {result.error or '—'}"
            )
        self.core.save()
        self._invalidate_caches()

    def _invalidate_caches(self) -> None:
        """Сброс access- и verification-ключей разом — любая правка политики ломает оба."""
        self.cache.invalidate_all_access()
        self.cache.invalidate_verification()

    @staticmethod
    def _rule_type_str(value: Any) -> str:
        return value if isinstance(value, str) else value.value

    @staticmethod
    def _effective_is_active(rule_type: str, data: PolicyCreate) -> bool:
        # композит активен, пока активны его подусловия — собственный флаг бессмыслен
        if _is_composite(rule_type):
            return True
        return bool(getattr(data, "is_active", True))

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

    def _snapshot_policy(self, policy: Any) -> dict:
        snap: dict = {p: getattr(policy, p, None) for p in _SNAPSHOT_SCALAR_PROPS}
        for p in _SNAPSHOT_LIST_PROPS:
            snap[p] = list(getattr(policy, p, []) or [])
        return snap

    def _restore_policy(self, policy: Any, snap: dict) -> None:
        for p in _SNAPSHOT_SCALAR_PROPS:
            setattr(policy, p, snap[p])
        for p in _SNAPSHOT_LIST_PROPS:
            setattr(policy, p, list(snap[p]))

    def _reset_policy_fields(self, policy: Any) -> None:
        for p in _SNAPSHOT_SCALAR_PROPS:
            if p in _RESET_EXCLUDED:
                continue
            setattr(policy, p, None)
        for p in _SNAPSHOT_LIST_PROPS:
            setattr(policy, p, [])

    def _delete_policies_by_id(self, ids: List[str]) -> None:
        for pid in ids:
            pol = self.core.policies.find_by_id(pid)
            if pol is not None:
                self.core.policies.delete(pol)

    def _check_cycle(self, policy_data: PolicyCreate) -> None:
        # без source это подполитика композита — в граф зависимостей не попадает
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

    def _materialize_nested(self, data: PolicyCreate) -> tuple[PolicyCreate, List[str]]:
        """Создать вложенные подусловия композита; при сбое уже созданные удалить."""
        nested = list(getattr(data, "nested_subpolicies", None) or [])
        if not nested:
            return data, []
        created: List[str] = []
        for child in nested:
            child_copy = child.model_copy(update={
                "source_element_id": None,
                "is_active": True,
                "nested_subpolicies": None,
            })
            try:
                child_dict = self.create_policy(child_copy)
            except Exception:
                self._delete_policies_by_id(created)
                raise
            created.append(child_dict["id"])
        merged_ids = list(data.subpolicy_ids or []) + created
        updated = data.model_copy(update={
            "subpolicy_ids": merged_ids,
            "nested_subpolicies": None,
        })
        return updated, created

    def _attach_to_source(self, policy: Any, source_element_id: Optional[str]) -> Any:
        if not source_element_id:
            return None
        source = self.core.courses.find_by_id(source_element_id)
        if not source:
            source = self.core.courses.get_or_create_element(source_element_id, COURSE_STRUCTURE_OWL_CLASS)
        source.has_access_policy.append(policy)
        return source

    def _apply_type_specific_fields(
        self,
        policy: Any,
        data: PolicyCreate,
        rule_type: str,
    ) -> None:
        self._apply_common_fields(policy, data)
        handler = REGISTRY.get(rule_type)
        if handler is not None:
            handler.apply_abox_fields(policy, data, self.core)

    def _apply_common_fields(self, policy: Any, data: PolicyCreate) -> None:
        if data.passing_threshold is not None:
            policy.passing_threshold = data.passing_threshold
        if data.valid_from:
            policy.valid_from = data.valid_from
        if data.valid_until:
            policy.valid_until = data.valid_until
        if data.target_element_id:
            target = self.core.courses.find_by_id(data.target_element_id)
            if not target:
                target = self.core.courses.get_or_create_element(data.target_element_id, COURSE_STRUCTURE_OWL_CLASS)
            policy.targets_element = target
        if data.target_competency_id:
            # competency не CourseStructure, поэтому courses.find_by_id не подходит
            comp_cls = getattr(self.core.onto, "Competency", None)
            comp = (
                self.core.onto.search_one(type=comp_cls, iri=f"*{data.target_competency_id}")
                if comp_cls is not None
                else None
            )
            if comp is None:
                raise ValueError(f"Компетенция {data.target_competency_id} не найдена.")
            policy.targets_competency = [comp]

    def _rollback_policy(self, policy_node: Any, source_node: Any) -> None:
        try:
            if policy_node in source_node.has_access_policy:
                source_node.has_access_policy.remove(policy_node)
            self.core.policies.delete(policy_node)
        except Exception:
            logger.exception("Откат политики %s не удался", getattr(policy_node, "name", "?"))

    def _cleanup_orphan_nested(self, parent_policy: Any, old_subs: List[Any]) -> None:
        """Удалить подусловия, которые висели только в parent_policy и больше нигде."""
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
