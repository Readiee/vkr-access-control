"""Базовый класс хэндлера типа правила доступа."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import networkx as nx

if TYPE_CHECKING:
    from schemas import PolicyCreate
    from core.ontology_core import OntologyCore
    from services.verification.graph_validator import ProbePolicy


class RuleHandler:
    """Поведение одного типа правила: граф зависимостей, probe, верификация, ABox, описание.

    Дефолты — no-op: типы, у которых метод семантически пуст
    (date/group не дают структурных дуг; completion/grade/viewed не пишут ABox),
    наследуют без override.
    """

    rule_type: str = ""

    def add_dependency_edges(
        self,
        graph: nx.DiGraph,
        onto: Any,
        policy: Any,
        source_id: str,
        recurse: Callable,
        depth: int,
    ) -> None: ...

    def add_probe_edges(
        self,
        graph: nx.DiGraph,
        onto: Any,
        probe: "ProbePolicy",
        recurse_policy: Callable,
    ) -> None: ...

    def atomic_unsat_reason(self, onto: Any, policy: Any) -> Optional[str]:
        return None

    def can_grant(
        self,
        onto: Any,
        policy: Any,
        can_grant_element: Callable,
        can_grant_policy: Callable,
        visited: set,
        cache: Dict[str, bool],
        unsat_policies: set,
    ) -> bool:
        return True

    def describe(self, policy: Any) -> str:
        from utils.owl_utils import get_owl_prop
        return get_owl_prop(policy, "rule_type", "") or policy.name

    def apply_abox_fields(
        self,
        policy: Any,
        data: "PolicyCreate",
        core: "OntologyCore",
    ) -> None: ...
