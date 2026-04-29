"""Split-node DiGraph над структурой курса и политиками доступа

Дуги: интра-элементные, иерархические и политические. Политические строятся
по rule_type: completion/grade/aggregate/competency → tgt.complete → src.access,
viewed_required → tgt.access → src.access, date/group дуг не добавляют,
and/or раскрываются рекурсией по has_subpolicy
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

import networkx as nx

from core.enums import RuleType
from utils.owl_utils import get_owl_prop

# импорт откладывается до первого вызова: избегает кругового импорта при старте
def _registry():
    from services.rule_handlers import REGISTRY
    return REGISTRY


@dataclass
class ProbePolicy:
    """Описание пробной политики для детектора циклов при создании правила"""
    rule_type: str
    source_id: str
    target_element_id: Optional[str] = None
    target_competency_id: Optional[str] = None
    subpolicy_ids: List[str] = field(default_factory=list)
    aggregate_element_ids: List[str] = field(default_factory=list)


class GraphValidator:
    """Детектор циклов по split-node графу зависимостей"""

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
        """Проверить, порождает ли пробная политика цикл; вернуть путь или []"""
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
        """Вернуть все циклы в графе зависимостей онтологии"""
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
        """Собрать split-node граф по всей онтологии"""
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
        handler = _registry().get(rule_type)
        if handler is not None:
            handler.add_dependency_edges(graph, onto, policy, source_id, cls._add_policy_edges, depth)

    @classmethod
    def _add_probe_edges(cls, graph: nx.DiGraph, onto: Any, probe: ProbePolicy) -> None:
        handler = _registry().get(probe.rule_type)
        if handler is not None:
            handler.add_probe_edges(graph, onto, probe, cls._add_policy_edges)

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
        """Родитель элемента по has_module/contains_activity; None при отсутствии"""
        for candidate in onto.CourseStructure.instances():
            children = list(getattr(candidate, "has_module", []) or []) + list(
                getattr(candidate, "contains_activity", []) or []
            )
            for child in children:
                if child.name == element_id:
                    return candidate
        return None
