"""Хэндлеры атомарных типов правил доступа."""
from __future__ import annotations

from typing import Any

from core.enums import RuleType
from services.rule_handlers._base import RuleHandler
from utils.owl_utils import get_owl_prop, label_or_name


class CompletionHandler(RuleHandler):
    rule_type = RuleType.COMPLETION.value

    def add_dependency_edges(self, graph, _onto, policy, source_id, _recurse, _depth):
        target = get_owl_prop(policy, "targets_element")
        if target is not None:
            graph.add_edge(f"{target.name}_complete", f"{source_id}_access")

    def add_probe_edges(self, graph, _onto, probe, _recurse_policy):
        if probe.target_element_id:
            graph.add_edge(f"{probe.target_element_id}_complete", f"{probe.source_id}_access")

    def can_grant(self, _onto, policy, can_grant_element, _can_grant_policy, visited, cache, unsat_policies):
        target = get_owl_prop(policy, "targets_element")
        return can_grant_element(target, visited, cache, unsat_policies) if target else False

    def describe(self, policy):
        target = get_owl_prop(policy, "targets_element")
        return f"Завершить «{label_or_name(target)}»" if target else "Завершить ?"


class ViewedHandler(RuleHandler):
    rule_type = RuleType.VIEWED.value

    def add_dependency_edges(self, graph, _onto, policy, source_id, _recurse, _depth):
        target = get_owl_prop(policy, "targets_element")
        if target is not None:
            graph.add_edge(f"{target.name}_access", f"{source_id}_access")

    def add_probe_edges(self, graph, _onto, probe, _recurse_policy):
        if probe.target_element_id:
            graph.add_edge(f"{probe.target_element_id}_access", f"{probe.source_id}_access")

    def can_grant(self, _onto, policy, can_grant_element, _can_grant_policy, visited, cache, unsat_policies):
        target = get_owl_prop(policy, "targets_element")
        return can_grant_element(target, visited, cache, unsat_policies) if target else False

    def describe(self, policy):
        target = get_owl_prop(policy, "targets_element")
        return f"Просмотреть «{label_or_name(target)}»" if target else "Просмотреть ?"


class GradeHandler(RuleHandler):
    rule_type = RuleType.GRADE.value

    def add_dependency_edges(self, graph, _onto, policy, source_id, _recurse, _depth):
        target = get_owl_prop(policy, "targets_element")
        if target is not None:
            graph.add_edge(f"{target.name}_complete", f"{source_id}_access")

    def add_probe_edges(self, graph, _onto, probe, _recurse_policy):
        if probe.target_element_id:
            graph.add_edge(f"{probe.target_element_id}_complete", f"{probe.source_id}_access")

    def atomic_unsat_reason(self, _onto, policy):
        th = get_owl_prop(policy, "passing_threshold")
        if th is None or th < 0 or th > 100:
            return f"threshold={th} вне диапазона [0, 100]"
        return None

    def can_grant(self, _onto, policy, can_grant_element, _can_grant_policy, visited, cache, unsat_policies):
        target = get_owl_prop(policy, "targets_element")
        return can_grant_element(target, visited, cache, unsat_policies) if target else False

    def describe(self, policy):
        target = get_owl_prop(policy, "targets_element")
        threshold = get_owl_prop(policy, "passing_threshold")
        return f"Оценка ≥ {threshold} за «{label_or_name(target)}»" if target else f"Оценка ≥ {threshold}"


class CompetencyHandler(RuleHandler):
    rule_type = RuleType.COMPETENCY.value

    def add_dependency_edges(self, graph, onto, policy, source_id, _recurse, _depth):
        competency = get_owl_prop(policy, "targets_competency")
        if competency is None:
            return
        for assessor in onto.search(assesses=competency) or []:
            graph.add_edge(f"{assessor.name}_complete", f"{source_id}_access")
        for sub in _subcompetencies(onto, competency):
            for assessor in onto.search(assesses=sub) or []:
                graph.add_edge(f"{assessor.name}_complete", f"{source_id}_access")

    def add_probe_edges(self, graph, onto, probe, _recurse_policy):
        if not probe.target_competency_id:
            return
        competency = onto.search_one(type=onto.Competency, iri=f"*{probe.target_competency_id}")
        if competency is None:
            return
        # Probe дублирует дуги реальной политики, иначе цикл через транзитивную
        # иерархию компетенций не виден на этапе создания правила.
        for assessor in onto.search(assesses=competency) or []:
            graph.add_edge(f"{assessor.name}_complete", f"{probe.source_id}_access")
        for sub in _subcompetencies(onto, competency):
            for assessor in onto.search(assesses=sub) or []:
                graph.add_edge(f"{assessor.name}_complete", f"{probe.source_id}_access")

    def atomic_unsat_reason(self, onto, policy):
        comp = get_owl_prop(policy, "targets_competency")
        if comp is None:
            return "targets_competency не задано"
        if not _competency_is_assessed(onto, comp):
            return f"компетенция {comp.name} не оценивается ни одним элементом"
        return None

    def can_grant(self, onto, policy, can_grant_element, _can_grant_policy, visited, cache, unsat_policies):
        comp = get_owl_prop(policy, "targets_competency")
        if comp is None:
            return False
        for assessor in onto.search(assesses=comp) or []:
            if can_grant_element(assessor, visited, cache, unsat_policies):
                return True
        for sub in onto.search(is_subcompetency_of=comp) or []:
            for assessor in onto.search(assesses=sub) or []:
                if can_grant_element(assessor, visited, cache, unsat_policies):
                    return True
        return False

    def describe(self, policy):
        comp = get_owl_prop(policy, "targets_competency")
        return f"Компетенция «{label_or_name(comp)}»" if comp else "Компетенция ?"


class DateHandler(RuleHandler):
    rule_type = RuleType.DATE.value

    def atomic_unsat_reason(self, _onto, policy):
        vf = get_owl_prop(policy, "valid_from")
        vu = get_owl_prop(policy, "valid_until")
        if vf is None or vu is None:
            return "отсутствует valid_from или valid_until"
        if vf > vu:
            return f"пустое окно: valid_from={vf} > valid_until={vu}"
        return None

    def describe(self, policy):
        vf = get_owl_prop(policy, "valid_from")
        vu = get_owl_prop(policy, "valid_until")
        fmt = lambda d: d.strftime("%d.%m.%Y") if d else "?"
        return f"Доступно {fmt(vf)} – {fmt(vu)}"


class GroupHandler(RuleHandler):
    rule_type = RuleType.GROUP.value

    def apply_abox_fields(self, policy, data, core):
        if not data.restricted_to_group_id:
            return
        group = core.onto.search_one(type=core.onto.Group, iri=f"*{data.restricted_to_group_id}")
        if group is None:
            raise ValueError(f"Группа {data.restricted_to_group_id} не найдена.")
        policy.restricted_to_group = group

    def describe(self, policy):
        group = get_owl_prop(policy, "restricted_to_group")
        return f"Только группа «{label_or_name(group)}»" if group else "Только группа ?"


class AggregateHandler(RuleHandler):
    rule_type = RuleType.AGGREGATE.value

    _FN_LABELS = {"AVG": "Средний балл", "SUM": "Сумма баллов", "COUNT": "Количество сданных"}

    def add_dependency_edges(self, graph, _onto, policy, source_id, _recurse, _depth):
        for elem in getattr(policy, "aggregate_elements", []) or []:
            graph.add_edge(f"{elem.name}_complete", f"{source_id}_access")

    def add_probe_edges(self, graph, _onto, probe, _recurse_policy):
        for eid in probe.aggregate_element_ids:
            graph.add_edge(f"{eid}_complete", f"{probe.source_id}_access")

    def atomic_unsat_reason(self, _onto, policy):
        elements = list(getattr(policy, "aggregate_elements", []) or [])
        if not elements:
            return "aggregate_elements пуст"
        fn = get_owl_prop(policy, "aggregate_function") or "AVG"
        th = get_owl_prop(policy, "passing_threshold")
        k = len(elements)
        max_val = {"AVG": 100.0, "SUM": 100.0 * k, "COUNT": float(k)}.get(fn.upper(), 100.0)
        if th is None or th < 0 or th > max_val:
            return f"threshold={th} вне диапазона [0, {max_val}] для fn={fn}, k={k}"
        return None

    def can_grant(self, _onto, policy, can_grant_element, _can_grant_policy, visited, cache, unsat_policies):
        elements = list(getattr(policy, "aggregate_elements", []) or [])
        return all(can_grant_element(e, visited, cache, unsat_policies) for e in elements)

    def describe(self, policy):
        fn = get_owl_prop(policy, "aggregate_function") or "AVG"
        fn_ru = self._FN_LABELS.get(fn, fn)
        threshold = get_owl_prop(policy, "passing_threshold")
        elems = list(getattr(policy, "aggregate_elements", []) or [])
        names = ", ".join(f"«{label_or_name(e)}»" for e in elems)
        return f"{fn_ru} по {names} ≥ {threshold}" if names else f"{fn_ru} ≥ {threshold}"

    def apply_abox_fields(self, policy, data, core):
        fn = data.aggregate_function
        policy.aggregate_function = fn.value if hasattr(fn, "value") else fn
        agg_elements = []
        for eid in data.aggregate_element_ids or []:
            elem = core.courses.find_by_id(eid)
            if elem is None:
                raise ValueError(f"Элемент агрегата {eid} не найден.")
            agg_elements.append(elem)
        policy.aggregate_elements = agg_elements


def _subcompetencies(onto: Any, parent: Any) -> set:
    """BFS по is_subcompetency_of; root в результат не входит."""
    seen: set = set()
    frontier = [parent]
    while frontier:
        node = frontier.pop()
        for child in onto.search(is_subcompetency_of=node) or []:
            if child not in seen:
                seen.add(child)
                frontier.append(child)
    return seen


def _competency_is_assessed(onto: Any, competency: Any) -> bool:
    frontier = [competency]
    seen: set = set()
    while frontier:
        node = frontier.pop()
        seen.add(node.name)
        if onto.search(assesses=node):
            return True
        for sub in onto.search(is_subcompetency_of=node) or []:
            if sub.name not in seen:
                frontier.append(sub)
    return False
