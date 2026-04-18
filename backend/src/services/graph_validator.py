import networkx as nx
from typing import List, Any

class GraphValidator:
    """Валидатор графа зависимостей и иерархии курса."""

    @staticmethod
    def check_for_cycles(onto: Any, new_source_id: str, new_target_id: str) -> List[str]:
        """
        Проверка цикла в графе зависимостей (Split-Node DiGraph).
        
        Каждый элемент разделен на узел доступа (_access) и завершения (_complete).
        Это позволяет корректно обрабатывать транзитивные циклы в иерархии.
        """
        G = nx.DiGraph()

        # Построение базовой иерархии и внутренних связей
        for el in onto.CourseStructure.instances():
            eid = el.name
            # Чтобы завершить элемент, нужно сначала получить к нему доступ
            G.add_edge(f"{eid}_access", f"{eid}_complete")

            children = (
                list(getattr(el, "has_module", []))
                + list(getattr(el, "contains_element", []))
            )
            for child in children:
                cid = child.name
                # Доступ к дочернему элементу требует доступа к родителю
                G.add_edge(f"{eid}_access", f"{cid}_access")
                # Завершение родителя требует завершения всех детей
                G.add_edge(f"{cid}_complete", f"{eid}_complete")

        # Добавление активных политик доступа
        for policy in onto.AccessPolicy.instances():
            is_active = getattr(policy, "is_active", [True])
            if is_active and is_active[0] is False:
                continue
                
            source_elements = onto.search(has_access_policy=policy)
            targets = getattr(policy, "targets_element", [])
            
            if not targets or not source_elements:
                continue
                
            target_id = targets[0].name
            for source in source_elements:
                # Завершение target разблокирует доступ к source
                G.add_edge(f"{target_id}_complete", f"{source.name}_access")

        # Добавление проверяемой политики
        G.add_edge(f"{new_target_id}_complete", f"{new_source_id}_access")

        try:
            cycle_edges = nx.find_cycle(G, orientation="original")
            path: List[str] = []
            for u, _, _ in cycle_edges:
                base_id = u.replace("_access", "").replace("_complete", "")
                if not path or path[-1] != base_id:
                    path.append(base_id)
            return path
        except nx.NetworkXNoCycle:
            return []

    @staticmethod
    def get_parent_of(onto: Any, element_id: str) -> Any:
        """Поиск родительского объекта в иерархии курса."""
        el = onto.search_one(iri=f"*{element_id}")
        if not el:
            return None
            
        for candidate in onto.CourseStructure.instances():
            if el in getattr(candidate, "has_module", []):
                return candidate
            if el in getattr(candidate, "contains_element", []):
                return candidate
        return None
