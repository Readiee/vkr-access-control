"""Чтение доступа студента к элементам курса.

CWA-enforcement (default-deny для элементов с политиками, у которых не
выведен is_available_for) + каскадная блокировка по иерархии. На вход берёт
результат последнего reasoning-прогона из ABox (is_available_for), на выход —
Redis-кэш + матрица HTTP-ответа.

date_restricted не фильтруется здесь: окно целиком обсчитывается SWRL-шаблоном 5
через CurrentTime, и элемент за пределами окна не получит is_available_for.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Set

from core.enums import RuleType
from services.explanation_service import ExplanationService, Justification
from services.ontology_core import OntologyCore
from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)


class AccessService:
    """Сборка матрицы доступа и объяснений блокировки для студента."""

    def __init__(self, core: OntologyCore) -> None:
        self.core = core
        self.explainer = ExplanationService(core)

    def rebuild_student_access(self, student_id: str) -> Dict[str, Any]:
        """Пройти CWA-enforcement по всем элементам и записать в Redis."""
        student = self._resolve_student(student_id)
        if student is None:
            return {"status": "error", "message": f"Студент {student_id} не найден."}

        inferred = self._compute_inferred_access(student)
        self.core.cache.set_student_access(student_id, inferred)
        return {
            "student_id": student_id,
            "inferred_available_elements": list(inferred.keys()),
            "inferred_access": inferred,
        }

    def get_course_access(self, student_id: str, course_id: str) -> Dict[str, List[str]]:
        """Вернуть доступные элементы в рамках курса, с учётом каскадной блокировки."""
        cached = self.core.cache.get_student_access(student_id)
        if cached is None:
            # Redis может быть недоступен — CacheService.set_student_access тогда no-op.
            # Берём результат rebuild напрямую, не полагаясь на возврат cache.get.
            rebuild = self.rebuild_student_access(student_id)
            cached = rebuild.get("inferred_access", {})

        course_elements = self._collect_course_elements(course_id)
        parent_map = self._build_parent_map()
        visible: Set[str] = set()
        for eid in course_elements:
            if self._is_really_available(eid, cached, parent_map):
                visible.add(eid)
        return {"available_elements": list(visible)}

    def explain_blocking(self, student_id: str, element_id: str) -> Dict[str, Any]:
        """Собрать объяснение, почему конкретный элемент (не)доступен студенту."""
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

        parent_blocker = self._find_parent_blocker(element, student)
        cascade = parent_blocker["element_id"] if parent_blocker else None
        is_available = satisfies_on_element and cascade is None
        if not applicable:
            is_available = cascade is None  # default-allow для свободного контента

        justification = self._collect_justification(student, element, applicable)

        return {
            "element_id": element_id,
            "student_id": student_id,
            "is_available": is_available,
            "cascade_blocker": cascade,
            "cascade_reason": parent_blocker["reason"] if parent_blocker else None,
            "applicable_policies": applicable,
            "justification": justification,
        }

    def _collect_justification(
        self, student: Any, element: Any, applicable: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Trace вывода is_available_for по мета-правилу SWRL.

        Для satisfied политик возвращает binding тела, для unsatisfied — те же
        биндинги с недостающим атомом. У элемента без активных политик — тривиальный
        default-allow-узел, CWA.
        """
        if not applicable:
            return {
                "status": "available",
                "rule_template": "default_allow",
                "note": "У элемента нет активных политик — CWA-default-allow.",
            }
        tree: Justification = self.explainer.explain_is_available(student, element)
        return _justification_to_dict(tree)

    def _compute_inferred_access(self, student: Any) -> Dict[str, Dict[str, Any]]:
        """Прогнать CWA-enforcement: элемент доступен, если (нет политик) ИЛИ (is_available_for),
        причём родительские элементы тоже доступны.
        """
        inferred: Dict[str, Dict[str, Any]] = {}
        for elem in self.core.courses.get_all_elements():
            active = [
                pol for pol in getattr(elem, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            swrl_passed = not active or student in (getattr(elem, "is_available_for", []) or [])
            if not swrl_passed:
                continue
            if not self._parent_unlocked(elem, student):
                continue
            inferred[elem.name] = {}
        return inferred

    def _parent_unlocked(self, element: Any, student: Any) -> bool:
        for parent in self.core.courses.get_all_elements():
            children = list(getattr(parent, "has_module", []) or []) + list(
                getattr(parent, "contains_element", []) or []
            )
            if element not in children:
                continue
            parent_active = [
                pol for pol in getattr(parent, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            if parent_active and student not in (getattr(parent, "is_available_for", []) or []):
                return False
            return self._parent_unlocked(parent, student)
        return True

    def _find_parent_blocker(self, element: Any, student: Any) -> Optional[Dict[str, str]]:
        for parent in self.core.courses.get_all_elements():
            children = list(getattr(parent, "has_module", []) or []) + list(
                getattr(parent, "contains_element", []) or []
            )
            if element not in children:
                continue
            parent_active = [
                pol for pol in getattr(parent, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            if parent_active and student not in (getattr(parent, "is_available_for", []) or []):
                return {
                    "element_id": parent.name,
                    "reason": f"Родитель {parent.name} недоступен по активной политике",
                }
            return self._find_parent_blocker(parent, student)
        return None

    def _describe_policy(self, policy: Any, student: Any) -> Dict[str, Any]:
        rule_type = get_owl_prop(policy, "rule_type", "")
        satisfied = policy in (getattr(student, "satisfies", []) or [])
        failure_reason = None
        witness: Dict[str, Any] = {}

        if not satisfied:
            failure_reason, witness = self._diagnose_failure(policy, rule_type, student)

        return {
            "policy_id": policy.name,
            "rule_type": rule_type,
            "satisfied": satisfied,
            "failure_reason": failure_reason,
            "witness": witness,
        }

    def _diagnose_failure(self, policy: Any, rule_type: str, student: Any) -> tuple[str, Dict[str, Any]]:
        target = get_owl_prop(policy, "targets_element")
        competency = get_owl_prop(policy, "targets_competency")
        if rule_type == RuleType.COMPETENCY.value and competency is not None:
            owned = [c.name for c in getattr(student, "has_competency", []) or []]
            return (
                f"У студента нет компетенции {competency.name}",
                {"required_competency": competency.name, "student_competencies": owned},
            )
        if rule_type == RuleType.GROUP.value:
            group = get_owl_prop(policy, "restricted_to_group")
            groups = [g.name for g in getattr(student, "belongs_to_group", []) or []]
            return (
                f"Студент не входит в группу {group.name if group else '(?)'}",
                {"required_group": group.name if group else None, "student_groups": groups},
            )
        if rule_type in {RuleType.COMPLETION.value, RuleType.VIEWED.value} and target is not None:
            return (
                f"Нет записи прогресса по элементу {target.name}",
                {"target_element": target.name},
            )
        if rule_type == RuleType.GRADE.value and target is not None:
            threshold = get_owl_prop(policy, "passing_threshold")
            return (
                f"Не достигнут порог оценки {threshold} на элементе {target.name}",
                {"target_element": target.name, "passing_threshold": threshold},
            )
        if rule_type == RuleType.DATE.value:
            return (
                "Текущее время вне валидного окна политики",
                {
                    "valid_from": str(get_owl_prop(policy, "valid_from") or ""),
                    "valid_until": str(get_owl_prop(policy, "valid_until") or ""),
                },
            )
        if rule_type == RuleType.AGGREGATE.value:
            threshold = get_owl_prop(policy, "passing_threshold")
            return (
                f"Агрегат не достиг порога {threshold}",
                {"passing_threshold": threshold},
            )
        if rule_type in {RuleType.AND.value, RuleType.OR.value}:
            subs = [sub.name for sub in getattr(policy, "has_subpolicy", []) or []]
            return "Композитная политика не выполнена целиком", {"subpolicies": subs}
        return "Условие политики не выполнено", {}

    def _resolve_student(self, student_id: str) -> Optional[Any]:
        node_id = student_id if student_id.startswith("student_") else f"student_{student_id}"
        return self.core.students.get_or_create(node_id)

    def _collect_course_elements(self, course_id: str) -> Set[str]:
        course = self.core.courses.find_by_id(course_id)
        if not course:
            return set()
        collected = {course.name}

        def walk(node: Any) -> None:
            for m in getattr(node, "has_module", []) or []:
                collected.add(m.name)
                walk(m)
            for a in getattr(node, "contains_element", []) or []:
                collected.add(a.name)
                walk(a)

        walk(course)
        return collected

    def _build_parent_map(self) -> Dict[str, str]:
        parent_map: Dict[str, str] = {}
        for parent in self.core.courses.get_all_elements():
            children: Iterable[Any] = list(getattr(parent, "has_module", []) or []) + list(
                getattr(parent, "contains_element", []) or []
            )
            for child in children:
                parent_map[child.name] = parent.name
        return parent_map

    def _is_really_available(self, eid: str, cache: Dict[str, Any], parent_map: Dict[str, str]) -> bool:
        if eid not in cache:
            return False
        parent = parent_map.get(eid)
        if parent is None:
            return True
        return self._is_really_available(parent, cache, parent_map)


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
