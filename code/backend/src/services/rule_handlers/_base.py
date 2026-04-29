"""Базовый класс хэндлера типа правила доступа

Каждый тип правила наследует RuleHandler и переопределяет нужные методы.
No-op defaults — для типов, у которых метод семантически пуст (например,
date/group не добавляют дуги в граф зависимостей).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import networkx as nx

if TYPE_CHECKING:
    from schemas.schemas import PolicyCreate
    from services.ontology_core import OntologyCore
    from services.graph_validator import ProbePolicy


class RuleHandler:
    """Протокол поведения одного типа правила доступа.

    Методы вызываются диспетчерами в GraphValidator, VerificationService,
    policy_formatters и PolicyService. Default-реализации — no-op или «разрешено».
    Конкретный тип переопределяет только те методы, где его семантика нетривиальна
    """

    rule_type: str = ""

    # ---- граф зависимостей ------------------------------------------------

    def add_dependency_edges(
        self,
        graph: nx.DiGraph,
        onto: Any,
        policy: Any,
        source_id: str,
        recurse: Callable,
        depth: int,
    ) -> None:
        """Добавить дуги для реальной политики из ABox"""

    def add_probe_edges(
        self,
        graph: nx.DiGraph,
        onto: Any,
        probe: "ProbePolicy",
        recurse_policy: Callable,
    ) -> None:
        """Добавить дуги для probe-политики при создании/обновлении"""

    # ---- верификация -------------------------------------------------------

    def atomic_unsat_reason(self, onto: Any, policy: Any) -> Optional[str]:
        """Вернуть причину невыполнимости или None, если политика корректна"""
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
        """Можно ли теоретически выполнить политику (структурная достижимость)"""
        return True

    # ---- форматирование ----------------------------------------------------

    def describe(self, policy: Any) -> str:
        """Строковое описание для UI (без rdfs:label)"""
        from utils.owl_utils import get_owl_prop
        return get_owl_prop(policy, "rule_type", "") or policy.name

    # ---- ABox write --------------------------------------------------------

    def apply_abox_fields(
        self,
        policy: Any,
        data: "PolicyCreate",
        core: "OntologyCore",
    ) -> None:
        """Перенести типо-специфичные поля из PolicyCreate в ABox-индивид"""
