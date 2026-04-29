"""SLD-trace тела SWRL для satisfies / is_available_for."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.enums import RuleType
from services.ontology_core import OntologyCore
from utils.owl_utils import get_owl_prop


@dataclass
class Justification:
    status: str  # satisfied | unsatisfied | available | unavailable
    rule_template: str
    policy_id: Optional[str] = None
    variable_bindings: Dict[str, Any] = field(default_factory=dict)
    body_facts: List[Dict[str, Any]] = field(default_factory=list)
    children: List["Justification"] = field(default_factory=list)
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class _AtomicSpec:
    template: str
    bindings: Dict[str, Any]
    body_facts: List[Dict[str, Any]]
    note_positive: str
    note_negative: str


class AccessExplainer:
    """Обоснование выведенных satisfies / is_available_for через SLD-trace тела SWRL.

    Приватный модуль; вызывается только из AccessService.
    """

    def __init__(self, core: OntologyCore) -> None:
        self.core = core

    def explain_is_available(self, student: Any, element: Any) -> Justification:
        """Trace мета-правила: is_available_for(el, s) ← has_access_policy(el, p) ∧ is_active(p) ∧ satisfies(s, p)."""
        active_policies = [
            p for p in (getattr(element, "has_access_policy", []) or [])
            if get_owl_prop(p, "is_active", True) is True
        ]
        children = [self.explain_satisfies(student, p) for p in active_policies]
        available = student in (getattr(element, "is_available_for", []) or [])
        witnesses = [c for c in children if c.status == "satisfied"]

        note = (
            f"Элемент доступен через активные политики: {[c.policy_id for c in witnesses]}."
            if available
            else "is_available_for не выведено: ни одна активная политика не дала satisfies."
        )
        return Justification(
            status="available" if available else "unavailable",
            rule_template="meta:is_available_for",
            variable_bindings={"element": element.name, "student": student.name},
            body_facts=[
                {"predicate": "has_access_policy", "subject": element.name, "object": p.name}
                for p in active_policies
            ],
            children=children,
            note=note,
        )

    def explain_satisfies(self, student: Any, policy: Any) -> Justification:
        satisfied = policy in (getattr(student, "satisfies", []) or [])
        rule_type = get_owl_prop(policy, "rule_type", "") or ""

        if rule_type in {RuleType.AND.value, RuleType.OR.value}:
            return self._explain_composite(student, policy, satisfied, rule_type)

        builder = self._ATOMIC_SPECS.get(rule_type)
        if builder is None:
            return Justification(
                status="satisfied" if satisfied else "unsatisfied",
                rule_template=f"unknown:{rule_type}",
                policy_id=policy.name,
                note="Неизвестный rule_type — шаблон не соответствует каталогу SWRL.",
            )
        spec = builder(self, student, policy)
        return Justification(
            status="satisfied" if satisfied else "unsatisfied",
            rule_template=spec.template,
            policy_id=policy.name,
            variable_bindings=spec.bindings,
            body_facts=spec.body_facts,
            note=spec.note_positive if satisfied else spec.note_negative,
        )

    def _explain_composite(
        self, student: Any, policy: Any, satisfied: bool, rule_type: str
    ) -> Justification:
        subs = list(getattr(policy, "has_subpolicy", []) or [])
        children = [self.explain_satisfies(student, sub) for sub in subs]
        facts = [{"predicate": "has_subpolicy", "subject": policy.name, "object": s.name} for s in subs]
        bindings: Dict[str, Any] = {
            "student": student.name, "policy": policy.name,
            "subpolicies": [s.name for s in subs],
        }
        if rule_type == RuleType.AND.value:
            template = "and_combination"
            failing = [c for c in children if c.status == "unsatisfied"]
            note = (
                "Все подполитики выполнены; AllDifferent гарантирует отсутствие унификации."
                if satisfied
                else f"Не выполнены подполитики: {[c.policy_id for c in failing]}."
            )
        else:
            template = "or_combination"
            passing = [c for c in children if c.status == "satisfied"]
            bindings["satisfied_by"] = [c.policy_id for c in passing]
            note = (
                f"Хотя бы одна подполитика выполнена: {[c.policy_id for c in passing]}."
                if satisfied
                else "Ни одна подполитика не выполнена."
            )
        return Justification(
            status="satisfied" if satisfied else "unsatisfied",
            rule_template=template,
            policy_id=policy.name,
            variable_bindings=bindings,
            body_facts=facts,
            children=children,
            note=note,
        )

    def _spec_completion(self, student: Any, policy: Any) -> _AtomicSpec:
        target = get_owl_prop(policy, "targets_element")
        pr = self._find_progress(student, target)
        bindings = {
            "student": student.name, "policy": policy.name,
            "target": target.name if target else None,
            "progress_record": pr.name if pr else None,
        }
        facts: List[Dict[str, Any]] = []
        if target is not None:
            facts.append({"predicate": "targets_element", "subject": policy.name, "object": target.name})
        if pr is not None:
            facts.append({"predicate": "has_progress_record", "subject": student.name, "object": pr.name})
            facts.append({
                "predicate": "refers_to_element", "subject": pr.name,
                "object": (get_owl_prop(pr, "refers_to_element") or target).name,
            })
            status = get_owl_prop(pr, "has_status")
            facts.append({
                "predicate": "has_status", "subject": pr.name,
                "object": status.name if status else None,
            })
        return _AtomicSpec(
            template="completion_required",
            bindings=bindings,
            body_facts=facts,
            note_positive="Body выполнено: найдена запись прогресса с has_status=status_completed.",
            note_negative=f"Нет ProgressRecord со status_completed для {target.name if target else '?'}.",
        )

    def _spec_grade(self, student: Any, policy: Any) -> _AtomicSpec:
        target = get_owl_prop(policy, "targets_element")
        threshold = get_owl_prop(policy, "passing_threshold")
        pr = self._find_progress(student, target)
        grade = get_owl_prop(pr, "has_grade") if pr else None
        bindings = {
            "student": student.name, "policy": policy.name,
            "target": target.name if target else None,
            "progress_record": pr.name if pr else None,
            "grade": grade, "threshold": threshold,
        }
        facts: List[Dict[str, Any]] = []
        if target is not None:
            facts.append({"predicate": "targets_element", "subject": policy.name, "object": target.name})
        facts.append({"predicate": "passing_threshold", "subject": policy.name, "object": threshold})
        if pr is not None:
            facts.append({"predicate": "has_grade", "subject": pr.name, "object": grade})
        return _AtomicSpec(
            template="grade_required",
            bindings=bindings,
            body_facts=facts,
            note_positive=f"Body выполнено: has_grade={grade} >= threshold={threshold}.",
            note_negative=f"Не выполнено grade≥threshold: {grade} vs {threshold}.",
        )

    def _spec_viewed(self, student: Any, policy: Any) -> _AtomicSpec:
        target = get_owl_prop(policy, "targets_element")
        pr = self._find_progress(student, target)
        status = get_owl_prop(pr, "has_status") if pr else None
        bindings = {
            "student": student.name, "policy": policy.name,
            "target": target.name if target else None,
            "progress_record": pr.name if pr else None,
            "status": status.name if status else None,
        }
        facts: List[Dict[str, Any]] = []
        if target is not None:
            facts.append({"predicate": "targets_element", "subject": policy.name, "object": target.name})
        if pr is not None:
            facts.append({
                "predicate": "has_status", "subject": pr.name,
                "object": status.name if status else None,
            })
        return _AtomicSpec(
            template="viewed_required",
            bindings=bindings,
            body_facts=facts,
            note_positive="Body выполнено: has_status=status_viewed.",
            note_negative=f"has_status={status.name if status else '∅'} ≠ status_viewed.",
        )

    def _spec_competency(self, student: Any, policy: Any) -> _AtomicSpec:
        comp = get_owl_prop(policy, "targets_competency")
        student_comps = list(getattr(student, "has_competency", []) or [])
        chain = self._find_competency_chain(student_comps, comp) if comp else []
        bindings = {
            "student": student.name, "policy": policy.name,
            "required_competency": comp.name if comp else None,
            "student_competencies": [c.name for c in student_comps],
        }
        facts: List[Dict[str, Any]] = []
        if comp is not None:
            facts.append({"predicate": "targets_competency", "subject": policy.name, "object": comp.name})
        for c in student_comps:
            facts.append({"predicate": "has_competency", "subject": student.name, "object": c.name})
        if chain and len(chain) > 1:
            for parent, child in zip(chain[1:], chain[:-1]):
                facts.append({"predicate": "is_subcompetency_of", "subject": child.name, "object": parent.name})
        if chain:
            note_positive = f"Body выполнено через иерархию: {' ⊑ '.join(c.name for c in chain)}."
        else:
            note_positive = "Body выполнено напрямую (has_competency)."
        note_negative = (
            f"У студента нет компетенции {comp.name if comp else '?'} ни прямо, ни через иерархию."
        )
        return _AtomicSpec(
            template="competency_required",
            bindings=bindings,
            body_facts=facts,
            note_positive=note_positive,
            note_negative=note_negative,
        )

    def _spec_date(self, student: Any, policy: Any) -> _AtomicSpec:
        vf = get_owl_prop(policy, "valid_from")
        vu = get_owl_prop(policy, "valid_until")
        now_ind = next(iter(self.core.onto.CurrentTime.instances()), None)
        now = get_owl_prop(now_ind, "has_value") if now_ind else None
        facts = [
            {"predicate": "valid_from", "subject": policy.name, "object": str(vf) if vf else None},
            {"predicate": "valid_until", "subject": policy.name, "object": str(vu) if vu else None},
            {"predicate": "has_value", "subject": now_ind.name if now_ind else None,
             "object": str(now) if now else None},
        ]
        return _AtomicSpec(
            template="date_restricted",
            bindings={
                "student": student.name, "policy": policy.name,
                "valid_from": str(vf) if vf else None,
                "valid_until": str(vu) if vu else None,
                "current_time": str(now) if now else None,
            },
            body_facts=facts,
            note_positive=f"Body выполнено: {vf} ≤ now={now} ≤ {vu}.",
            note_negative=f"Текущее время {now} вне окна [{vf}, {vu}].",
        )

    def _spec_group(self, student: Any, policy: Any) -> _AtomicSpec:
        required = get_owl_prop(policy, "restricted_to_group")
        groups = list(getattr(student, "belongs_to_group", []) or [])
        facts: List[Dict[str, Any]] = []
        if required is not None:
            facts.append({"predicate": "restricted_to_group", "subject": policy.name, "object": required.name})
        for g in groups:
            facts.append({"predicate": "belongs_to_group", "subject": student.name, "object": g.name})
        required_name = required.name if required else "?"
        return _AtomicSpec(
            template="group_restricted",
            bindings={
                "student": student.name, "policy": policy.name,
                "required_group": required.name if required else None,
                "student_groups": [g.name for g in groups],
            },
            body_facts=facts,
            note_positive=f"Body выполнено: студент входит в {required_name}.",
            note_negative=f"Студент не входит в {required_name}.",
        )

    def _spec_aggregate(self, student: Any, policy: Any) -> _AtomicSpec:
        threshold = get_owl_prop(policy, "passing_threshold")
        fn = get_owl_prop(policy, "aggregate_function") or "AVG"
        elements = list(getattr(policy, "aggregate_elements", []) or [])
        fact = self._find_aggregate_fact(student, policy)
        value = get_owl_prop(fact, "computed_value") if fact else None
        grades = [
            {
                "element": get_owl_prop(pr, "refers_to_element").name,
                "progress_record": pr.name,
                "grade": get_owl_prop(pr, "has_grade"),
            }
            for pr in (getattr(student, "has_progress_record", []) or [])
            if get_owl_prop(pr, "refers_to_element") in elements
            and get_owl_prop(pr, "has_grade") is not None
        ]
        facts = [
            {"predicate": "aggregate_function", "subject": policy.name, "object": fn},
            {"predicate": "passing_threshold", "subject": policy.name, "object": threshold},
        ]
        for e in elements:
            facts.append({"predicate": "aggregate_elements", "subject": policy.name, "object": e.name})
        if fact is not None:
            facts.append({"predicate": "computed_value", "subject": fact.name, "object": value})
        for g in grades:
            facts.append({"predicate": "has_grade", "subject": g["progress_record"], "object": g["grade"]})
        if fact is None:
            note_negative = f"Для студента нет AggregateFact (пустой набор оценок по {len(elements)} элементам)."
        else:
            note_negative = f"{fn} = {value} < {threshold}."
        return _AtomicSpec(
            template="aggregate_required",
            bindings={
                "student": student.name, "policy": policy.name,
                "function": fn, "threshold": threshold,
                "computed_value": value,
                "contributing_grades": grades,
            },
            body_facts=facts,
            note_positive=f"Body выполнено: {fn}({[g['grade'] for g in grades]}) = {value} >= {threshold}.",
            note_negative=note_negative,
        )

    def _find_progress(self, student: Any, element: Any) -> Optional[Any]:
        if element is None:
            return None
        for pr in getattr(student, "has_progress_record", []) or []:
            if get_owl_prop(pr, "refers_to_element") == element:
                return pr
        return None

    def _find_aggregate_fact(self, student: Any, policy: Any) -> Optional[Any]:
        for fact in self.core.onto.AggregateFact.instances():
            if get_owl_prop(fact, "for_student") == student and get_owl_prop(fact, "for_policy") == policy:
                return fact
        return None

    def _find_competency_chain(self, student_comps: List[Any], required: Any) -> List[Any]:
        """Цепочка ?sub ⊑* ?required, начинающаяся в student_comps.

        Возвращает [required, ..., sub], где sub ∈ student_comps; если required
        уже у студента — цепочка из одного элемента; если пути нет — [].
        """
        if required in student_comps:
            return [required]
        for comp in student_comps:
            visited = set()
            stack = [(comp, [comp])]
            while stack:
                node, path = stack.pop()
                if node == required:
                    return list(reversed(path))
                if node.name in visited:
                    continue
                visited.add(node.name)
                for parent in getattr(node, "is_subcompetency_of", []) or []:
                    stack.append((parent, path + [parent]))
        return []

    _ATOMIC_SPECS: Dict[str, Callable[["AccessExplainer", Any, Any], _AtomicSpec]] = {
        RuleType.COMPLETION.value: _spec_completion,
        RuleType.GRADE.value: _spec_grade,
        RuleType.VIEWED.value: _spec_viewed,
        RuleType.COMPETENCY.value: _spec_competency,
        RuleType.DATE.value: _spec_date,
        RuleType.GROUP.value: _spec_group,
        RuleType.AGGREGATE.value: _spec_aggregate,
    }
