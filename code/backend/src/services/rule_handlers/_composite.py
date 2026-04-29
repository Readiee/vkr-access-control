"""Хэндлеры составных (AND/OR) типов правил доступа."""
from __future__ import annotations

from owlready2 import AllDifferent

from core.enums import RuleType
from services.rule_handlers._base import RuleHandler


class AndHandler(RuleHandler):
    rule_type = RuleType.AND.value

    def add_dependency_edges(self, graph, onto, policy, source_id, recurse, depth):
        for sub in getattr(policy, "has_subpolicy", []) or []:
            recurse(graph, onto, sub, source_id, depth + 1)

    def add_probe_edges(self, graph, onto, probe, recurse_policy):
        for sub_id in probe.subpolicy_ids:
            sub = onto.search_one(type=onto.AccessPolicy, iri=f"*{sub_id}")
            if sub is not None:
                recurse_policy(graph, onto, sub, probe.source_id, depth=0)

    def can_grant(self, _onto, policy, _can_grant_element, can_grant_policy, visited, cache, unsat_policies):
        subs = list(getattr(policy, "has_subpolicy", []) or [])
        if not subs:
            return False
        return all(
            sub.name not in unsat_policies
            and can_grant_policy(sub, visited, cache, unsat_policies)
            for sub in subs
        )

    def describe(self, policy):
        subs = list(getattr(policy, "has_subpolicy", []) or [])
        if not subs:
            return "И-композит"
        from utils.policy_formatters import describe_policy_auto
        return " И ".join(describe_policy_auto(sub) for sub in subs)

    def apply_abox_fields(self, policy, data, core):
        if not data.subpolicy_ids:
            return
        subs = []
        for sub_id in data.subpolicy_ids:
            sub = core.policies.find_by_id(sub_id)
            if sub is None:
                raise ValueError(f"Подполитика {sub_id} не найдена.")
            subs.append(sub)
        policy.has_subpolicy = subs
        # OWL не делает unique name assumption: без AllDifferent SWRL может
        # унифицировать переменные sub1=sub2 и AND вырождается в OR.
        if len(subs) >= 2:
            AllDifferent(subs)


class OrHandler(RuleHandler):
    rule_type = RuleType.OR.value

    def add_dependency_edges(self, graph, onto, policy, source_id, recurse, depth):
        for sub in getattr(policy, "has_subpolicy", []) or []:
            recurse(graph, onto, sub, source_id, depth + 1)

    def add_probe_edges(self, graph, onto, probe, recurse_policy):
        for sub_id in probe.subpolicy_ids:
            sub = onto.search_one(type=onto.AccessPolicy, iri=f"*{sub_id}")
            if sub is not None:
                recurse_policy(graph, onto, sub, probe.source_id, depth=0)

    def can_grant(self, _onto, policy, _can_grant_element, can_grant_policy, visited, cache, unsat_policies):
        subs = list(getattr(policy, "has_subpolicy", []) or [])
        if not subs:
            return False
        return any(
            sub.name not in unsat_policies
            and can_grant_policy(sub, visited, cache, unsat_policies)
            for sub in subs
        )

    def describe(self, policy):
        subs = list(getattr(policy, "has_subpolicy", []) or [])
        if not subs:
            return "ИЛИ-композит"
        from utils.policy_formatters import describe_policy_auto
        return " ИЛИ ".join(describe_policy_auto(sub) for sub in subs)

    def apply_abox_fields(self, policy, data, core):
        if not data.subpolicy_ids:
            return
        subs = []
        for sub_id in data.subpolicy_ids:
            sub = core.policies.find_by_id(sub_id)
            if sub is None:
                raise ValueError(f"Подполитика {sub_id} не найдена.")
            subs.append(sub)
        policy.has_subpolicy = subs
