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
from services.access._explanations import AccessExplainer, Justification
from services.cache_manager import CacheManager
from services.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator
from utils.owl_utils import get_owl_prop
from utils.policy_formatters import policy_display_name

logger = logging.getLogger(__name__)


class AccessService:
    """Сборка матрицы доступа и объяснений блокировки для студента.

    По DSL §36 зависит от OntologyCore (ABox), CacheManager (cache-first чтение)
    и ReasoningOrchestrator (cache miss → reasoning). Зависимости инжектятся явно.
    """

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
        """Пройти CWA-enforcement по всем элементам и записать в Redis."""
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
        """Вернуть доступные элементы в рамках курса, с учётом каскадной блокировки."""
        cached = self.cache.get_student_access(student_id)
        if cached is None:
            # Redis может быть недоступен — CacheManager тогда no-op.
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

        parent_obj_map = self._build_parent_obj_map()
        parent_blocker = self._find_parent_blocker(element, student, parent_obj_map)
        cascade = parent_blocker["element_id"] if parent_blocker else None
        cascade_name = parent_blocker["element_name"] if parent_blocker else None
        is_available = satisfies_on_element and cascade is None
        if not applicable:
            is_available = cascade is None  # default-allow для свободного контента

        justification = self._collect_justification(student, element, applicable)

        return {
            "element_id": element_id,
            "element_name": _label_of(element),
            "student_id": student_id,
            "student_name": _label_of(student),
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
        parent_obj_map = self._build_parent_obj_map()
        inferred: Dict[str, Dict[str, Any]] = {}
        for elem in self.core.courses.get_all_elements():
            active = [
                pol for pol in getattr(elem, "has_access_policy", []) or []
                if get_owl_prop(pol, "is_active", True) is True
            ]
            swrl_passed = not active or student in (getattr(elem, "is_available_for", []) or [])
            if not swrl_passed:
                continue
            if not self._parent_unlocked(elem, student, parent_obj_map):
                continue
            inferred[elem.name] = {}
        return inferred

    def _build_parent_obj_map(self) -> Dict[str, Any]:
        """Один проход по CourseStructure: child.name → parent-object.

        Используется для каскадных проверок без повторного O(N) поиска родителя
        на каждый элемент.
        """
        mapping: Dict[str, Any] = {}
        for parent in self.core.courses.get_all_elements():
            children = list(getattr(parent, "has_module", []) or []) + list(
                getattr(parent, "contains_activity", []) or []
            )
            for child in children:
                mapping[child.name] = parent
        return mapping

    def _parent_unlocked(self, element: Any, student: Any, parent_obj_map: Dict[str, Any]) -> bool:
        parent = parent_obj_map.get(element.name)
        if parent is None:
            return True
        parent_active = [
            pol for pol in getattr(parent, "has_access_policy", []) or []
            if get_owl_prop(pol, "is_active", True) is True
        ]
        if parent_active and student not in (getattr(parent, "is_available_for", []) or []):
            return False
        return self._parent_unlocked(parent, student, parent_obj_map)

    def _find_parent_blocker(
        self, element: Any, student: Any, parent_obj_map: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        parent = parent_obj_map.get(element.name)
        if parent is None:
            return None
        parent_active = [
            pol for pol in getattr(parent, "has_access_policy", []) or []
            if get_owl_prop(pol, "is_active", True) is True
        ]
        if parent_active and student not in (getattr(parent, "is_available_for", []) or []):
            parent_label = _label_of(parent)
            return {
                "element_id": parent.name,
                "element_name": parent_label,
                "reason": f"Родительский элемент «{parent_label}» недоступен студенту",
            }
        return self._find_parent_blocker(parent, student, parent_obj_map)

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
        comp_name = _label_of(competency)
        owned = [_label_of(c) for c in getattr(student, "has_competency", []) or []]
        return (
            f"У студента нет компетенции «{comp_name}»",
            {"required_competency": comp_name, "student_competencies": owned},
        )

    def _diagnose_group(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        group = get_owl_prop(policy, "restricted_to_group")
        group_name = _label_of(group) if group else None
        groups = [_label_of(g) for g in getattr(student, "belongs_to_group", []) or []]
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
        t = _label_of(target)
        return f"Нужно {verb} элемент «{t}»", {"target_element": t}

    def _diagnose_grade(self, policy: Any, student: Any) -> tuple[str, Dict[str, Any]]:
        target = get_owl_prop(policy, "targets_element")
        if target is None:
            return self._diagnose_unknown(policy, student)
        threshold = get_owl_prop(policy, "passing_threshold")
        t = _label_of(target)
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
        # Sandbox-студент живёт под id "student_sandbox" — сначала ищем по
        # исходному id, чтобы не создавать фантомного Student с префиксом.
        found = self.core.onto.search_one(type=self.core.onto.Student, iri=f"*{student_id}")
        if found is not None:
            return found
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
            for a in getattr(node, "contains_activity", []) or []:
                collected.add(a.name)
                walk(a)

        walk(course)
        return collected

    def _build_parent_map(self) -> Dict[str, str]:
        parent_map: Dict[str, str] = {}
        for parent in self.core.courses.get_all_elements():
            children: Iterable[Any] = list(getattr(parent, "has_module", []) or []) + list(
                getattr(parent, "contains_activity", []) or []
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


def _label_of(owl_obj: Any) -> str:
    """Человечное название OWL-индивида: rdfs:label или снова ID."""
    if owl_obj is None:
        return ""
    label = getattr(owl_obj, "label", None)
    if label:
        return label[0]
    return owl_obj.name


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
