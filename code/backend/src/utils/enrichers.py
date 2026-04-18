"""Пайплайн пост-обработки выведенных доступов (паттерн Chain of Responsibility).

Каждый Enricher принимает OWL-индивид элемента и словарь с уже собранными
данными, дополняет его и возвращает обновлённый словарь.
Для добавления новой логики достаточно создать подкласс BaseEnricher
и зарегистрировать его в списке enrichers внутри register_progress.
"""
from __future__ import annotations
from core.enums import RuleType
from utils.owl_utils import get_owl_prop

# ===========================================================================
# 1 — Пост-обработка (обогащение) выведенных доступов
# ===========================================================================

class BaseEnricher:
    """Базовый класс пост-процессора элемента доступа."""

    def enrich(self, element_node: Any, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обогащает словарь данных об элементе.

        Args:
            element_node: OWL-индивид CourseStructure.
            current_data: Уже накопленные данные (передаётся по цепочке).

        Returns:
            Обновлённый словарь current_data.
        """
        raise NotImplementedError


class DateRestrictionEnricher(BaseEnricher):
    """Извлекает временные окна доступа из политик типа date_restricted."""

    def enrich(self, element_node: Any, current_data: Dict[str, Any]) -> Dict[str, Any]:
        from_date = None
        until_date = None

        if hasattr(element_node, "has_access_policy"):
            for policy in element_node.has_access_policy:
                if get_owl_prop(policy, "is_active", True) is False:
                    continue

                rule_type = get_owl_prop(policy, "rule_type")
                if rule_type == RuleType.DATE.value:
                    from_date = get_owl_prop(policy, "available_from")
                    until_date = get_owl_prop(policy, "available_until")
                    
                    if from_date and hasattr(from_date, "isoformat"): from_date = from_date.isoformat()
                    if until_date and hasattr(until_date, "isoformat"): until_date = until_date.isoformat()

        if from_date:
            current_data["available_from"] = from_date
        if until_date:
            current_data["available_until"] = until_date

        return current_data


# Здесь в будущем можно добавить: AttemptLimitEnricher, PaymentStatusEnricher и т.д.

# ===========================================================================
# 2 — Фильтры доступов
# ===========================================================================

class BaseAccessFilter:
    """Базовый класс фильтра доступов на этапе чтения из кэша."""

    def is_valid(self, element_data: Dict[str, Any]) -> bool:
        """Возвращает True, если элемент проходит фильтр.

        Args:
            element_data: Словарь с данными элемента из Redis.
        """
        raise NotImplementedError


class DateAccessFilter(BaseAccessFilter):
    """Фильтр: проверяет временное окно available_from / available_until."""

    def is_valid(self, element_data: Dict[str, Any]) -> bool:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        def parse_date(d_val):
            if not d_val: return None
            try:
                d_str = str(d_val).replace("Z", "+00:00")
                return datetime.fromisoformat(d_str)
            except Exception as e:
                import logging
                logging.warning(f"Ошибка парсинга даты: {d_val} - {e}")
                return None

        from_dt = parse_date(element_data.get("available_from"))
        until_dt = parse_date(element_data.get("available_until"))

        if from_dt:
            if from_dt.tzinfo is None: from_dt = from_dt.replace(tzinfo=timezone.utc)
            if now < from_dt: return False

        if until_dt:
            if until_dt.tzinfo is None: until_dt = until_dt.replace(tzinfo=timezone.utc)
            if now > until_dt: return False

        return True


# Здесь в будущем можно добавить: AttemptLimitFilter, PaymentStatusFilter и т.д.

