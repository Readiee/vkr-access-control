"""Обнаружение избыточных (СВ-4) и поглощённых (СВ-5) политик.

Синтаксические эвристики на парах политик: для grade_required и date_restricted
включение условий проверяется численно (пороги, окна), для group_restricted —
через вложенность групп. Полная DL-subsumption через Pellet на временных ABox
оставлена как точка расширения (MVP — без запуска Pellet, единицы миллисекунд).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from core.enums import RuleType
from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)


@dataclass
class SubsumptionPair:
    dominant: str
    dominated: str
    element: Optional[str]
    kind: str           # "redundancy" (СВ-4) | "subject_subsumption" (СВ-5)
    witness: str


class SubsumptionChecker:
    """Проверка всех пар (P1, P2) активных политик на поглощение."""

    def __init__(self, onto: Any) -> None:
        self.onto = onto

    def find_all(self) -> List[SubsumptionPair]:
        """Вернуть все пары с P1 subsumes P2 по синтаксическим правилам."""
        active = self._active_policies()
        reports: List[SubsumptionPair] = []
        seen: set[tuple[str, str]] = set()
        for p1 in active:
            for p2 in active:
                if p1 is p2:
                    continue
                key = (p1.name, p2.name)
                if key in seen:
                    continue
                result = self._check_pair(p1, p2)
                if result is None:
                    continue
                seen.add(key)
                reports.append(result)
        return reports

    def _active_policies(self) -> List[Any]:
        return [
            p for p in self.onto.AccessPolicy.instances()
            if get_owl_prop(p, "is_active", True) is True
        ]

    def _check_pair(self, p1: Any, p2: Any) -> Optional[SubsumptionPair]:
        rt1 = get_owl_prop(p1, "rule_type", "")
        rt2 = get_owl_prop(p2, "rule_type", "")
        element = self._common_element(p1, p2)

        # СВ-4 Redundancy: одинаковый тип + одинаковый target + более слабое условие поглощает более сильное
        if rt1 == rt2 and rt1 == RuleType.GRADE.value and element is not None:
            t1 = get_owl_prop(p1, "targets_element")
            t2 = get_owl_prop(p2, "targets_element")
            th1 = get_owl_prop(p1, "passing_threshold")
            th2 = get_owl_prop(p2, "passing_threshold")
            if t1 is not None and t2 is not None and t1.name == t2.name and th1 is not None and th2 is not None:
                if th1 <= th2 and th1 != th2:
                    return SubsumptionPair(
                        dominant=p1.name,
                        dominated=p2.name,
                        element=element,
                        kind="redundancy",
                        witness=f"grade≥{th2} ⊑ grade≥{th1}",
                    )

        if rt1 == rt2 and rt1 == RuleType.DATE.value and element is not None:
            from1 = get_owl_prop(p1, "valid_from")
            until1 = get_owl_prop(p1, "valid_until")
            from2 = get_owl_prop(p2, "valid_from")
            until2 = get_owl_prop(p2, "valid_until")
            if None not in (from1, until1, from2, until2):
                if from1 <= from2 and until1 >= until2 and (from1 != from2 or until1 != until2):
                    return SubsumptionPair(
                        dominant=p1.name,
                        dominated=p2.name,
                        element=element,
                        kind="redundancy",
                        witness=f"окно [{from2}, {until2}] ⊆ [{from1}, {until1}]",
                    )

        # СВ-5 Subject Subsumption: group_restricted с вложенной группой поглощается более широкой политикой
        if rt1 == rt2 and rt1 == RuleType.GROUP.value and element is not None:
            g1 = get_owl_prop(p1, "restricted_to_group")
            g2 = get_owl_prop(p2, "restricted_to_group")
            if g1 is not None and g2 is not None and g1.name != g2.name:
                if self._subgroup(g2, g1):
                    return SubsumptionPair(
                        dominant=p1.name,
                        dominated=p2.name,
                        element=element,
                        kind="subject_subsumption",
                        witness=f"группа {g2.name} ⊆ {g1.name}",
                    )

        # completion/viewed с одинаковым target — полное равенство → redundancy
        if rt1 == rt2 and rt1 in {RuleType.COMPLETION.value, RuleType.VIEWED.value} and element is not None:
            t1 = get_owl_prop(p1, "targets_element")
            t2 = get_owl_prop(p2, "targets_element")
            if t1 is not None and t2 is not None and t1.name == t2.name and p1.name < p2.name:
                return SubsumptionPair(
                    dominant=p1.name,
                    dominated=p2.name,
                    element=element,
                    kind="redundancy",
                    witness=f"{rt1}({t1.name}) — полное совпадение",
                )

        # СВ-5 AND-composite: atomic p1, AND p2 с подполитикой, синтаксически равной p1
        # — все subjects p2 удовлетворяют p1 через ту же подполитику; p1 поглощает p2.
        if rt2 == RuleType.AND.value and element is not None:
            sub_match = self._find_equivalent_subpolicy(p1, p2)
            if sub_match is not None:
                return SubsumptionPair(
                    dominant=p1.name,
                    dominated=p2.name,
                    element=element,
                    kind="subject_subsumption",
                    witness=f"{p1.name} ≡ {sub_match.name} ∈ subpolicies({p2.name})",
                )

        return None

    def _find_equivalent_subpolicy(self, atomic: Any, composite: Any) -> Optional[Any]:
        """Найти в подполитиках composite ту, что синтаксически эквивалентна atomic.

        Эквивалентность — совпадение rule_type + всех ключевых атрибутов (target,
        threshold, окно, группа, компетенция). Композитные подполитики не учитываем,
        чтобы не подменять глубокий DL-subsumption.
        """
        for sub in list(getattr(composite, "has_subpolicy", []) or []):
            if self._atomic_equivalent(atomic, sub):
                return sub
        return None

    def _atomic_equivalent(self, a: Any, b: Any) -> bool:
        rt_a = get_owl_prop(a, "rule_type", "")
        rt_b = get_owl_prop(b, "rule_type", "")
        if rt_a != rt_b or rt_a in {RuleType.AND.value, RuleType.OR.value}:
            return False
        if rt_a in {RuleType.COMPLETION.value, RuleType.VIEWED.value}:
            return self._same_ref(a, b, "targets_element")
        if rt_a == RuleType.GRADE.value:
            return self._same_ref(a, b, "targets_element") and \
                   get_owl_prop(a, "passing_threshold") == get_owl_prop(b, "passing_threshold")
        if rt_a == RuleType.COMPETENCY.value:
            return self._same_ref(a, b, "targets_competency")
        if rt_a == RuleType.GROUP.value:
            return self._same_ref(a, b, "restricted_to_group")
        if rt_a == RuleType.DATE.value:
            return get_owl_prop(a, "valid_from") == get_owl_prop(b, "valid_from") and \
                   get_owl_prop(a, "valid_until") == get_owl_prop(b, "valid_until")
        return False

    def _same_ref(self, a: Any, b: Any, prop: str) -> bool:
        va = get_owl_prop(a, prop)
        vb = get_owl_prop(b, prop)
        return va is not None and vb is not None and va.name == vb.name

    def _common_element(self, p1: Any, p2: Any) -> Optional[str]:
        sources1 = {s.name for s in (self.onto.search(has_access_policy=p1) or [])}
        sources2 = {s.name for s in (self.onto.search(has_access_policy=p2) or [])}
        shared = sources1 & sources2
        return next(iter(shared)) if shared else None

    def _subgroup(self, narrow: Any, wide: Any) -> bool:
        """Вернуть True, если narrow ⊆ wide через belongs_to_group студентов."""
        if narrow is wide:
            return False
        members_narrow = self._members(narrow)
        members_wide = self._members(wide)
        if not members_narrow:
            return False
        return members_narrow.issubset(members_wide)

    def _members(self, group: Any) -> set:
        result = set()
        for student in self.onto.Student.instances():
            if group in (getattr(student, "belongs_to_group", []) or []):
                result.add(student.name)
        return result
