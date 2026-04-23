"""Split-node DiGraph над структурой курса и политиками доступа.

Интра-элементные, иерархические и политические дуги. Политические дуги строятся
по rule_type: completion/grade/aggregate/competency → tgt.complete → src.access,
viewed_required → tgt.access → src.access, date/group → не добавляют дуг,
and/or → рекурсия по has_subpolicy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import networkx as nx

from core.enums import RuleType
from utils.owl_utils import get_owl_prop


@dataclass
class ProbePolicy:
    """Описание «пробной» политики для детектора циклов в UC-3."""
    rule_type: str
    source_id: str
    target_element_id: Optional[str] = None
    target_competency_id: Optional[str] = None
    subpolicy_ids: List[str] = field(default_factory=list)
    aggregate_element_ids: List[str] = field(default_factory=list)


class GraphValidator:
    """Детектор циклов по split-node графу зависимостей."""

    _MAX_RECURSION_DEPTH = 32  # защита от циклической композиции has_subpolicy

    @classmethod
    def check_for_cycles(
        cls,
        onto: Any,
        new_source_id: str,
        new_target_id: Optional[str] = None,
        rule_type: str = RuleType.COMPLETION.value,
        probe: Optional[ProbePolicy] = None,
    ) -> List[str]:
        """Проверить, порождает ли пробная политика цикл (UC-3). Вернуть путь или []."""
        if probe is None:
            probe = ProbePolicy(
                rule_type=rule_type,
                source_id=new_source_id,
                target_element_id=new_target_id,
            )
        graph = cls.build_dependency_graph(onto)
        cls._add_probe_edges(graph, onto, probe)
        return cls._find_first_cycle_path(graph)

    @classmethod
    def find_all_cycles(cls, onto: Any) -> List[List[str]]:
        """Вернуть все циклы в графе зависимостей онтологии (UC-6)."""
        graph = cls.build_dependency_graph(onto)
        cycles: List[List[str]] = []
        for component in nx.strongly_connected_components(graph):
            if len(component) < 2:
                node = next(iter(component))
                if graph.has_edge(node, node):
                    cycles.append([cls._strip_suffix(node)])
                continue
            subgraph = graph.subgraph(component).copy()
            try:
                edges = nx.find_cycle(subgraph, orientation="original")
            except nx.NetworkXNoCycle:
                continue
            cycles.append(cls._reconstruct_path(edges))
        return cycles

    @classmethod
    def build_dependency_graph(cls, onto: Any) -> nx.DiGraph:
        """Собрать split-node DiGraph по всей онтологии."""
        graph = nx.DiGraph()

        for elem in onto.CourseStructure.instances():
            eid = elem.name
            graph.add_edge(f"{eid}_access", f"{eid}_complete")
            children = list(getattr(elem, "has_module", []) or []) + list(
                getattr(elem, "contains_activity", []) or []
            )
            for child in children:
                cid = child.name
                graph.add_edge(f"{eid}_access", f"{cid}_access")
                graph.add_edge(f"{cid}_complete", f"{eid}_complete")

        for policy in onto.AccessPolicy.instances():
            if get_owl_prop(policy, "is_active", True) is False:
                continue
            sources = onto.search(has_access_policy=policy) or []
            for source in sources:
                cls._add_policy_edges(graph, onto, policy, source.name, depth=0)

        return graph

    @classmethod
    def _add_policy_edges(
        cls,
        graph: nx.DiGraph,
        onto: Any,
        policy: Any,
        source_id: str,
        depth: int,
    ) -> None:
        if depth > cls._MAX_RECURSION_DEPTH:
            raise RuntimeError(
                f"Превышена глубина has_subpolicy ({depth}); вероятна циклическая композиция"
            )

        rule_type = get_owl_prop(policy, "rule_type", "")
        if rule_type in {RuleType.DATE.value, RuleType.GROUP.value}:
            return

        if rule_type in {RuleType.COMPLETION.value, RuleType.GRADE.value}:
            target = get_owl_prop(policy, "targets_element")
            if target is not None:
                graph.add_edge(f"{target.name}_complete", f"{source_id}_access")
            return

        if rule_type == RuleType.VIEWED.value:
            target = get_owl_prop(policy, "targets_element")
            if target is not None:
                graph.add_edge(f"{target.name}_access", f"{source_id}_access")
            return

        if rule_type == RuleType.COMPETENCY.value:
            competency = get_owl_prop(policy, "targets_competency")
            if competency is None:
                return
            for assessor in onto.search(assesses=competency) or []:
                graph.add_edge(f"{assessor.name}_complete", f"{source_id}_access")
            for sub in cls._subcompetencies(onto, competency):
                for assessor in onto.search(assesses=sub) or []:
                    graph.add_edge(f"{assessor.name}_complete", f"{source_id}_access")
            return

        if rule_type in {RuleType.AND.value, RuleType.OR.value}:
            for sub in getattr(policy, "has_subpolicy", []) or []:
                cls._add_policy_edges(graph, onto, sub, source_id, depth + 1)
            return

        if rule_type == RuleType.AGGREGATE.value:
            for elem in getattr(policy, "aggregate_elements", []) or []:
                graph.add_edge(f"{elem.name}_complete", f"{source_id}_access")
            return

    @classmethod
    def _add_probe_edges(cls, graph: nx.DiGraph, onto: Any, probe: ProbePolicy) -> None:
        rt = probe.rule_type
        src = probe.source_id
        if rt in {RuleType.DATE.value, RuleType.GROUP.value}:
            return
        if rt in {RuleType.COMPLETION.value, RuleType.GRADE.value} and probe.target_element_id:
            graph.add_edge(f"{probe.target_element_id}_complete", f"{src}_access")
            return
        if rt == RuleType.VIEWED.value and probe.target_element_id:
            graph.add_edge(f"{probe.target_element_id}_access", f"{src}_access")
            return
        if rt == RuleType.COMPETENCY.value and probe.target_competency_id:
            competency = onto.search_one(type=onto.Competency, iri=f"*{probe.target_competency_id}")
            if competency is None:
                return
            for assessor in onto.search(assesses=competency) or []:
                graph.add_edge(f"{assessor.name}_complete", f"{src}_access")
            return
        if rt == RuleType.AGGREGATE.value:
            for eid in probe.aggregate_element_ids:
                graph.add_edge(f"{eid}_complete", f"{src}_access")
            return
        if rt in {RuleType.AND.value, RuleType.OR.value}:
            for sub_id in probe.subpolicy_ids:
                sub = onto.search_one(type=onto.AccessPolicy, iri=f"*{sub_id}")
                if sub is not None:
                    cls._add_policy_edges(graph, onto, sub, src, depth=0)

    @staticmethod
    def _subcompetencies(onto: Any, parent: Any) -> Set[Any]:
        seen: Set[Any] = set()
        frontier = [parent]
        while frontier:
            node = frontier.pop()
            for child in onto.search(is_subcompetency_of=node) or []:
                if child not in seen:
                    seen.add(child)
                    frontier.append(child)
        return seen

    @classmethod
    def _find_first_cycle_path(cls, graph: nx.DiGraph) -> List[str]:
        try:
            edges = nx.find_cycle(graph, orientation="original")
        except nx.NetworkXNoCycle:
            return []
        return cls._reconstruct_path(edges)

    @staticmethod
    def _reconstruct_path(edges: Any) -> List[str]:
        path: List[str] = []
        for edge in edges:
            u = edge[0]
            base = GraphValidator._strip_suffix(u)
            if not path or path[-1] != base:
                path.append(base)
        return path

    @staticmethod
    def _strip_suffix(node: str) -> str:
        if node.endswith("_access"):
            return node[: -len("_access")]
        if node.endswith("_complete"):
            return node[: -len("_complete")]
        return node

    @staticmethod
    def get_parent_of(onto: Any, element_id: str) -> Any:
        """Найти родителя элемента по has_module/contains_activity (совместимость)."""
        element = onto.search_one(type=onto.CourseStructure, iri=f"*{element_id}")
        if not element:
            return None
        for candidate in onto.CourseStructure.instances():
            if element in (getattr(candidate, "has_module", []) or []):
                return candidate
            if element in (getattr(candidate, "contains_activity", []) or []):
                return candidate
        return None
