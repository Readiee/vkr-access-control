"""Полная верификация курса: СВ-1 Consistency + СВ-2 Acyclicity + СВ-3 Reachability,
опционально — СВ-4 Redundancy и СВ-5 Subsumption через SubsumptionChecker.

Запуск reasoning проходит через ReasoningOrchestrator (pre-enrich + Pellet).
При таймауте reasoning отчёт помечается partial=True и СВ-1/2/3 выставляются в unknown.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.enums import RuleType
from services.cache_manager import CacheManager
from services.graph_validator import GraphValidator
from services.ontology_core import OntologyCore
from services.reasoning import ReasoningOrchestrator
from services.verification._subsumption import SubsumptionChecker
from utils.owl_utils import get_owl_prop
from utils.policy_formatters import policy_display_name

logger = logging.getLogger(__name__)


@dataclass
class PropertyReport:
    status: str               # "passed" | "failed" | "unknown"
    violations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VerificationReport:
    course_id: str
    run_id: str
    timestamp: str
    duration_ms: int
    partial: bool
    properties: Dict[str, PropertyReport]
    ontology_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        props = {}
        for name, report in self.properties.items():
            entry: Dict[str, Any] = {"status": report.status, "violations": report.violations}
            props[name] = entry

        passed = sum(1 for r in self.properties.values() if r.status == "passed")
        total = len(self.properties)
        summary = f"{passed} из {total} свойств выполнены"
        return {
            "course_id": self.course_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "partial": self.partial,
            "properties": props,
            "summary": summary,
            "ontology_version": self.ontology_version,
        }


def _covers(cached: Dict[str, Any], include_subsumption: bool) -> bool:
    props = cached.get("properties", {})
    if "consistency" not in props or "acyclicity" not in props or "reachability" not in props:
        return False
    if include_subsumption and ("redundancy" not in props or "subsumption" not in props):
        return False
    return True


def _report_from_dict(data: Dict[str, Any]) -> VerificationReport:
    props: Dict[str, PropertyReport] = {}
    for name, payload in (data.get("properties") or {}).items():
        props[name] = PropertyReport(
            status=payload.get("status", "unknown"),
            violations=payload.get("violations", []) or [],
        )
    return VerificationReport(
        course_id=data.get("course_id", ""),
        run_id=data.get("run_id", ""),
        timestamp=data.get("timestamp", ""),
        duration_ms=int(data.get("duration_ms", 0)),
        partial=bool(data.get("partial", False)),
        properties=props,
        ontology_version=data.get("ontology_version"),
    )


class VerificationService:
    """Единая точка запуска СВ-1…СВ-5.

    По DSL §37, §106–§108: зависит от OntologyCore, ReasoningOrchestrator
    (СВ-1 consistency + СВ-4/5 subsumption), GraphValidator (СВ-2/3 через
    статические методы), CacheManager (чтение и запись отчёта).
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

    def verify(
        self,
        course_id: str,
        include_subsumption: bool = False,
        use_cache: bool = True,
    ) -> VerificationReport:
        """Прогнать СВ-1/2/3 (+ СВ-4/5 при include_subsumption) и собрать отчёт.

        При use_cache=True возвращает сохранённый в Redis результат, если он есть и
        покрывает запрошенный набор свойств. Инвалидация кэша — на стороне
        PolicyService / IntegrationService при мутациях ABox.
        """
        if use_cache:
            cached = self.cache.get_verification(course_id)
            if cached and _covers(cached, include_subsumption):
                return _report_from_dict(cached)

        started = time.monotonic()
        run_id = uuid.uuid4().hex

        consistency = PropertyReport(status="unknown")
        acyclicity = PropertyReport(status="unknown")
        reachability = PropertyReport(status="unknown")
        redundancy = PropertyReport(status="unknown")
        subsumption = PropertyReport(status="unknown")

        course = self.core.courses.find_by_id(course_id)
        if course is None:
            raise LookupError(f"Курс {course_id} не найден")

        reasoning_result = self.reasoner.reason()
        partial = reasoning_result.status in {"timeout", "error"}

        # СВ-1 Consistency
        if reasoning_result.status == "ok":
            consistency.status = "passed"
        elif reasoning_result.status == "inconsistent":
            consistency.status = "failed"
            consistency.violations.append({
                "code": "SV1_INCONSISTENT",
                "message": reasoning_result.error or "Pellet: онтология inconsistent",
            })
        else:
            consistency.status = "unknown"
            consistency.violations.append({
                "code": "SV1_REASONING_" + reasoning_result.status.upper(),
                "message": reasoning_result.error or f"status={reasoning_result.status}",
            })

        # СВ-2 Acyclicity — всегда считается (чистый граф, независим от Pellet)
        cycles = GraphValidator.find_all_cycles(self.core.onto)
        if cycles:
            acyclicity.status = "failed"
            for cycle in cycles:
                acyclicity.violations.append({
                    "code": "SV2_CYCLE",
                    "path": cycle,
                    "path_names": [self._label_by_id(eid) for eid in cycle],
                    "policies": self._policies_on_cycle(cycle),
                    "policy_names": [self._label_by_id(pid) for pid in self._policies_on_cycle(cycle)],
                })
        else:
            acyclicity.status = "passed"

        # СВ-3 Reachability — только если консистентно (иначе смысла в структурном анализе нет)
        if consistency.status == "passed":
            unreachable = self._find_unreachable(course)
            if unreachable:
                reachability.status = "failed"
                reachability.violations = unreachable
            else:
                reachability.status = "passed"

        # СВ-4 / СВ-5 — по запросу
        if include_subsumption and consistency.status == "passed":
            pairs = SubsumptionChecker(self.core.onto).find_all()
            for pair in pairs:
                entry = {
                    "code": "SV4_REDUNDANT" if pair.kind == "redundancy" else "SV5_SUBSUMED",
                    "dominant": pair.dominant,
                    "dominant_name": self._label_by_id(pair.dominant),
                    "dominated": pair.dominated,
                    "dominated_name": self._label_by_id(pair.dominated),
                    "element": pair.element,
                    "element_name": self._label_by_id(pair.element) if pair.element else None,
                    "witness": pair.witness,
                }
                if pair.kind == "redundancy":
                    redundancy.violations.append(entry)
                else:
                    subsumption.violations.append(entry)
            redundancy.status = "failed" if redundancy.violations else "passed"
            subsumption.status = "failed" if subsumption.violations else "passed"

        duration_ms = int((time.monotonic() - started) * 1000)
        properties: Dict[str, PropertyReport] = {
            "consistency": consistency,
            "acyclicity": acyclicity,
            "reachability": reachability,
        }
        if include_subsumption:
            properties["redundancy"] = redundancy
            properties["subsumption"] = subsumption

        report = VerificationReport(
            course_id=course_id,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
            partial=partial,
            properties=properties,
            ontology_version=self.cache.current_ontology_version(),
        )

        if use_cache and not partial:
            self.cache.set_verification(course_id, report.to_dict())

        return report

    # ------------------------------------------------------------------
    # СВ-3 Reachability
    # ------------------------------------------------------------------
    def _find_unreachable(self, course: Any) -> List[Dict[str, Any]]:
        """Проходы 1 и 2 из А4: атомарная невыполнимость + структурная достижимость."""
        reports: List[Dict[str, Any]] = []
        atomic_unsat = self._atomic_unsatisfiable()
        reports.extend(atomic_unsat)
        unsat_ids = {entry["policy_id"] for entry in atomic_unsat}

        course_elements = self._collect_course_elements(course)
        cache: Dict[str, bool] = {}
        for element in course_elements:
            if not self._can_grant_element(element, visited=set(), cache=cache, unsat_policies=unsat_ids):
                reports.append({
                    "code": "SV3_UNREACHABLE",
                    "element_id": element.name,
                    "element_name": element.label[0] if getattr(element, "label", None) else element.name,
                    "reason": "Не найден путь удовлетворения ни одной политики на элементе",
                })
        return reports

    def _atomic_unsatisfiable(self) -> List[Dict[str, Any]]:
        unsat: List[Dict[str, Any]] = []
        for policy in self.core.onto.AccessPolicy.instances():
            if get_owl_prop(policy, "is_active", True) is False:
                continue
            reason = self._atomic_check(policy)
            if reason is not None:
                unsat.append({
                    "code": "SV3_ATOMIC_UNSAT",
                    "policy_id": policy.name,
                    "policy_name": policy_display_name(policy),
                    "rule_type": get_owl_prop(policy, "rule_type", ""),
                    "reason": reason,
                })
        return unsat

    def _atomic_check(self, policy: Any) -> Optional[str]:
        rt = get_owl_prop(policy, "rule_type", "")
        if rt == RuleType.GRADE.value:
            th = get_owl_prop(policy, "passing_threshold")
            if th is None or th < 0 or th > 100:
                return f"threshold={th} вне диапазона [0, 100]"
        elif rt == RuleType.DATE.value:
            vf = get_owl_prop(policy, "valid_from")
            vu = get_owl_prop(policy, "valid_until")
            if vf is None or vu is None:
                return "отсутствует valid_from или valid_until"
            if vf > vu:
                return f"пустое окно: valid_from={vf} > valid_until={vu}"
        elif rt == RuleType.AGGREGATE.value:
            elements = list(getattr(policy, "aggregate_elements", []) or [])
            if not elements:
                return "aggregate_elements пуст"
            fn = get_owl_prop(policy, "aggregate_function") or "AVG"
            th = get_owl_prop(policy, "passing_threshold")
            k = len(elements)
            max_val = {"AVG": 100.0, "SUM": 100.0 * k, "COUNT": float(k)}.get(fn.upper(), 100.0)
            if th is None or th < 0 or th > max_val:
                return f"threshold={th} вне диапазона [0, {max_val}] для fn={fn}, k={k}"
        elif rt == RuleType.COMPETENCY.value:
            comp = get_owl_prop(policy, "targets_competency")
            if comp is None:
                return "targets_competency не задано"
            if not self._competency_is_assessed(comp):
                return f"компетенция {comp.name} не оценивается ни одним элементом"
        return None

    def _competency_is_assessed(self, competency: Any) -> bool:
        frontier = [competency]
        seen = set()
        while frontier:
            node = frontier.pop()
            seen.add(node.name)
            if self.core.onto.search(assesses=node):
                return True
            for sub in self.core.onto.search(is_subcompetency_of=node) or []:
                if sub.name not in seen:
                    frontier.append(sub)
        return False

    def _can_grant_element(
        self,
        element: Any,
        visited: set,
        cache: Dict[str, bool],
        unsat_policies: set,
    ) -> bool:
        eid = element.name
        if eid in cache:
            return cache[eid]
        if eid in visited:
            cache[eid] = False
            return False
        visited = visited | {eid}

        parent = GraphValidator.get_parent_of(self.core.onto, eid)
        if parent is not None and not self._can_grant_element(parent, visited, cache, unsat_policies):
            cache[eid] = False
            return False

        active = [
            p for p in getattr(element, "has_access_policy", []) or []
            if get_owl_prop(p, "is_active", True) is True
        ]
        if not active:
            cache[eid] = True
            return True

        for policy in active:
            if policy.name in unsat_policies:
                continue
            if self._can_grant_policy(policy, visited, cache, unsat_policies):
                cache[eid] = True
                return True

        cache[eid] = False
        return False

    def _can_grant_policy(
        self,
        policy: Any,
        visited: set,
        cache: Dict[str, bool],
        unsat_policies: set,
    ) -> bool:
        rt = get_owl_prop(policy, "rule_type", "")
        if rt in {RuleType.COMPLETION.value, RuleType.GRADE.value, RuleType.VIEWED.value}:
            target = get_owl_prop(policy, "targets_element")
            if target is None:
                return False
            return self._can_grant_element(target, visited, cache, unsat_policies)
        if rt == RuleType.COMPETENCY.value:
            comp = get_owl_prop(policy, "targets_competency")
            if comp is None:
                return False
            for assessor in self.core.onto.search(assesses=comp) or []:
                if self._can_grant_element(assessor, visited, cache, unsat_policies):
                    return True
            for sub in self.core.onto.search(is_subcompetency_of=comp) or []:
                for assessor in self.core.onto.search(assesses=sub) or []:
                    if self._can_grant_element(assessor, visited, cache, unsat_policies):
                        return True
            return False
        if rt == RuleType.AGGREGATE.value:
            elements = list(getattr(policy, "aggregate_elements", []) or [])
            return all(self._can_grant_element(e, visited, cache, unsat_policies) for e in elements)
        if rt in {RuleType.DATE.value, RuleType.GROUP.value}:
            return True
        if rt == RuleType.AND.value:
            subs = list(getattr(policy, "has_subpolicy", []) or [])
            if not subs:
                return False
            return all(
                sub.name not in unsat_policies
                and self._can_grant_policy(sub, visited, cache, unsat_policies)
                for sub in subs
            )
        if rt == RuleType.OR.value:
            subs = list(getattr(policy, "has_subpolicy", []) or [])
            if not subs:
                return False
            return any(
                sub.name not in unsat_policies
                and self._can_grant_policy(sub, visited, cache, unsat_policies)
                for sub in subs
            )
        return True

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _collect_course_elements(self, course: Any) -> List[Any]:
        collected: List[Any] = [course]
        seen = {course.name}

        def walk(node: Any) -> None:
            for child in list(getattr(node, "has_module", []) or []) + list(
                getattr(node, "contains_activity", []) or []
            ):
                if child.name in seen:
                    continue
                seen.add(child.name)
                collected.append(child)
                walk(child)

        walk(course)
        return collected

    def _label_by_id(self, entity_id: str) -> str:
        if not entity_id:
            return ""
        ind = self.core.onto.search_one(iri=f"*{entity_id}")
        if ind is None:
            return entity_id
        if isinstance(ind, self.core.onto.AccessPolicy):
            return policy_display_name(ind)
        return ind.label[0] if getattr(ind, "label", None) else ind.name

    def _policies_on_cycle(self, cycle_path: List[str]) -> List[str]:
        """Вернуть имена политик, чьи источники попадают в путь цикла."""
        policy_ids: List[str] = []
        cycle_set = set(cycle_path)
        for policy in self.core.onto.AccessPolicy.instances():
            if get_owl_prop(policy, "is_active", True) is False:
                continue
            for source in self.core.onto.search(has_access_policy=policy) or []:
                if source.name in cycle_set:
                    policy_ids.append(policy.name)
                    break
        return policy_ids
