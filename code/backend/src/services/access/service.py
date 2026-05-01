"""Чтение доступа студента: default-deny и каскадная блокировка по родителям.

Дата-ограничения здесь не фильтруются — окно целиком обсчитывает SWRL через
CurrentTime, и за пределами окна is_available_for не выводится резонером.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from core.enums import JustificationStatus, RuleType
from services.access._explanations import AccessExplainer, Justification
from core.cache_manager import CacheManager
from core.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator
from utils.owl_utils import get_owl_prop, label_or_name
from utils.policy_formatters import policy_display_name

logger = logging.getLogger(__name__)

_DEFAULT_ALLOW_TEMPLATE = "default_allow"


class AccessService:
    def __init__(
        self,
        core: OntologyCore,
        *,
        cache: CacheManager,
        reasoner: ReasoningOrchestrator,
    ) -> None:
        self.core = core
        self.cache = cache
        self.reasoner = reasoner
        self.explainer = AccessExplainer(core)

    def rebuild_student_access(self, student_id: str) -> Dict[str, Any]:
        student = self._resolve_student(student_id)
        if student is None:
            return {"status": "error", "message": f"Студент {student_id} не найден."}

        inferred = self._compute_inferred_access(student)
        self.cache.set_student_access(student_id, inferred)
        return {
            "student_id": student_id,
            "inferred_available_elements": list(inferred.keys()),
            "inferred_access": inferred,
        }

    def get_course_access(self, student_id: str, course_id: str) -> Dict[str, List[str]]:
        cached = self.cache.get_student_access(student_id)
        if cached is None:
            # Redis недоступен — CacheManager — no-op; берём результат rebuild напрямую.
            rebuild = self.rebuild_student_access(student_id)
            cached = rebuild.get("inferred_access", {})

        course_elements = self._collect_course_elements(course_id)
        parent_index = self.core.courses.parent_index()
        visible: Set[str] = set()
        for eid in course_elements:
            if self._is_really_available(eid, cached, parent_index):
                visible.add(eid)
        return {"available_elements": list(visible)}

    def explain_blocking(self, student_id: str, element_id: str) -> Dict[str, Any]:
        student = self._resolve_student(student_id)
        element = self.core.courses.find_by_id(element_id)
        if student is None or element is None:
            raise ValueError(f"Студент {student_id} или элемент {element_id} не найден.")

        applicable = [
            self._describe_policy(pol, student)
            for pol in getattr(element, "has_access_policy", []) or []
            if get_owl_prop(pol, "is_active", True) is True
        ]
        satisfies_on_element = student in (getattr(element, "is_available_for", []) or [])

        parent_index = self.core.courses.parent_index()
        parent_blocker = self._find_parent_blocker(element, student, parent_index)
        cascade = parent_blocker["element_id"] if parent_blocker else None
        cascade_name = parent_blocker["element_name"] if parent_blocker else None
        is_available = satisfies_on_element and cascade is None
        if not applicable:
            is_available = cascade is None  # свободный контент — default-allow

        justification = self._collect_justification(student, element, applicable)

        return {
            "element_id": element_id,
            "element_name": label_or_name(element),
            "student_id": student_id,
            "student_name": label_or_name(student),
            "is_available": is_available,
            "cascade_blocker": cascade,
            "cascade_blocker_name": cascade_name,
            "cascade_reason": parent_blocker["reason"] if parent_blocker else None,
            "applicable_policies": applicable,
            "justification": justification,
        }

    def _collect_justification(
        self, student: Any, element: Any, applicable: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not applicable:
            return {
                "status": JustificationStatus.AVAILABLE.value,
                "rule_template": _DEFAULT_ALLOW_TEMPLATE,
                "note": "У элемента нет активных политик — default-allow",
            }
        tree: Justification = self.explainer.explain_is_available(student, element)
        return _justification_to_dict(tree)

    def _compute_inferred_access(self, student: Any) -> Dict[str, Dict[str, Any]]:
        """Default-deny: элемент доступен, если (политик нет) ∨ (выведен is_available_for),
        и все его родители тоже доступны.
        """
        parent_index = self.core.courses.parent_index()
        inferred: Dict[str, Dict[str, Any]] = {}
        for elem in self.core.courses.get_all_elements():
            active = [
                pol for pol in getattr(elem, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            swrl_passed = not active or student in (getattr(elem, "is_available_for", []) or [])
            if not swrl_passed:
                continue
            if not self._parent_unlocked(elem, student, parent_index):
                continue
            inferred[elem.name] = {}
        return inferred

    def _parent_unlocked(self, element: Any, student: Any, parent_index: Dict[str, Any]) -> bool:
        node = element
        while True:
            parent = parent_index.get(node.name)
            if parent is None:
                return True
            parent_active = [
                pol for pol in getattr(parent, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            if parent_active and student not in (getattr(parent, "is_available_for", []) or []):
                return False
            node = parent

    def _find_parent_blocker(
        self, element: Any, student: Any, parent_index: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        node = element
        while True:
            parent = parent_index.get(node.name)
            if parent is None:
                return None
            parent_active = [
                pol for pol in getattr(parent, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            if parent_active and student not in (getattr(parent, "is_available_for", []) or []):
                parent_label = label_or_name(parent)
                return {
                    "element_id": parent.name,
                    "element_name": parent_label,
                    "reason": f"Родительский элемент «{parent_label}» недоступен студенту",
                }
            node = parent

    def _describe_policy(self, policy: Any, student: Any) -> Dict[str, Any]:
        rule_type = get_owl_prop(policy, "rule_type", "")
        satisfied = policy in (getattr(student, "satisfies", []) or [])
        failure_reason = None
        witness: Dict[str, Any] = {}

        if not satisfied:
            failure_reason, witness = self._diagnose_failure(policy, rule_type, student)

        return {
            "policy_id": policy.name,
            "policy_name": policy_display_name(policy),
            "rule_type": rule_type,
            "satisfied": satisfied,
            "failure_reason": failure_reason,
            "witness": witness,
        }

    def _diagnose_failure(self, policy: Any, rule_type: str, student: Any) -> tuple[str, Dict[str, Any]]:
        handler = self._FAILURE_HANDLERS.get(rule_type, type(self)._diagnose_unknown)
        return handler(self, policy, student)

    def _diagnose_competency(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        competency = get_owl_prop(policy, "targets_competency")
        if competency is None:
            return self._diagnose_unknown(policy, student)
        comp_name = label_or_name(competency)
        owned = [label_or_name(c) for c in getattr(student, "has_competency", []) or []]
        return (
            f"У студента нет компетенции «{comp_name}»",
            {"required_competency": comp_name, "student_competencies": owned},
        )

    def _diagnose_group(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        group = get_owl_prop(policy, "restricted_to_group")
        group_name = label_or_name(group) if group else None
        groups = [label_or_name(g) for g in getattr(student, "belongs_to_group", []) or []]
        return (
            f"Студент не входит в группу «{group_name or '?'}»",
            {"required_group": group_name, "student_groups": groups},
        )

    def _diagnose_completion(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        return self._diagnose_target_verb(policy, "завершить")

    def _diagnose_viewed(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        return self._diagnose_target_verb(policy, "просмотреть")

    def _diagnose_target_verb(self, policy: Any, verb: str) -> tuple[str, Dict[str, Any]]:
        target = get_owl_prop(policy, "targets_element")
        if target is None:
            return self._diagnose_unknown(policy, None)
        t = label_or_name(target)
        return f"Нужно {verb} элемент «{t}»", {"target_element": t}

    def _diagnose_grade(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        target = get_owl_prop(policy, "targets_element")
        if target is None:
            return self._diagnose_unknown(policy, student)
        threshold = get_owl_prop(policy, "passing_threshold")
        t = label_or_name(target)
        return (
            f"Не достигнут порог оценки {threshold} за «{t}»",
            {"target_element": t, "passing_threshold": threshold},
        )

    def _diagnose_date(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        return (
            "Текущее время вне окна доступа",
            {
                "valid_from": str(get_owl_prop(policy, "valid_from") or ""),
                "valid_until": str(get_owl_prop(policy, "valid_until") or ""),
            },
        )

    def _diagnose_aggregate(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        threshold = get_owl_prop(policy, "passing_threshold")
        fn = get_owl_prop(policy, "aggregate_function") or "AVG"
        return (
            f"Агрегат ({fn}) не достиг порога {threshold}",
            {"passing_threshold": threshold, "aggregate_function": fn},
        )

    def _diagnose_composite(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        rule_type = get_owl_prop(policy, "rule_type", "")
        subs = list(getattr(policy, "has_subpolicy", []) or [])
        details = []
        for sub in subs:
            sub_rt = get_owl_prop(sub, "rule_type", "")
            sub_satisfied = sub in (getattr(student, "satisfies", []) or [])
            sub_reason = None
            if not sub_satisfied:
                sub_reason, _ = self._diagnose_failure(sub, sub_rt, student)
            details.append({
                "id": sub.name,
                "name": policy_display_name(sub),
                "rule_type": sub_rt,
                "satisfied": sub_satisfied,
                "failure_reason": sub_reason,
            })
        prefix = "Не все условия выполнены" if rule_type == RuleType.AND.value else "Ни одно условие не выполнено"
        return prefix, {"subpolicies": details}

    def _diagnose_unknown(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        return "Условие правила не выполнено", {}

    _FAILURE_HANDLERS = {
        RuleType.COMPETENCY.value: _diagnose_competency,
        RuleType.GROUP.value: _diagnose_group,
        RuleType.COMPLETION.value: _diagnose_completion,
        RuleType.VIEWED.value: _diagnose_viewed,
        RuleType.GRADE.value: _diagnose_grade,
        RuleType.DATE.value: _diagnose_date,
        RuleType.AGGREGATE.value: _diagnose_aggregate,
        RuleType.AND.value: _diagnose_composite,
        RuleType.OR.value: _diagnose_composite,
    }

    def _resolve_student(self, student_id: str) -> Optional[Any]:
        # Сначала ищем по исходному id, чтобы sandbox-студент (student_sandbox)
        # не дублировался под student_student_sandbox.
        found = self.core.onto.search_one(type=self.core.onto.Student, iri=f"*{student_id}")
        if found is not None:
            return found
        node_id = student_id if student_id.startswith("student_") else f"student_{student_id}"
        return self.core.students.get_or_create(node_id)

    def _collect_course_elements(self, course_id: str) -> Set[str]:
        return self.core.courses.subtree_ids(course_id)

    def _is_really_available(self, eid: str, cache: Dict[str, Any], parent_index: Dict[str, Any]) -> bool:
        node_id = eid
        while True:
            if node_id not in cache:
                return False
            parent = parent_index.get(node_id)
            if parent is None:
                return True
            node_id = parent.name


def _justification_to_dict(node: Justification) -> Dict[str, Any]:
    return {
        "status": node.status,
        "rule_template": node.rule_template,
        "policy_id": node.policy_id,
        "variable_bindings": node.variable_bindings,
        "body_facts": node.body_facts,
        "note": node.note,
        "children": [_justification_to_dict(c) for c in node.children],
    }
