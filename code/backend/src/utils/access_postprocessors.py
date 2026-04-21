"""Пост-обработка результатов reasoning при сборке ответа API.

Два независимых этапа:
  - обогащение словаря данных об элементе полями из политик (временные окна и т.п.);
  - фильтрация элементов при чтении из кэша (например, проверка текущего времени
    относительно valid_from / valid_until).

Не путать со `services/ontology_enricher` — тот работает с ABox до reasoning,
здесь же идёт обработка dict-ов для HTTP-ответа после reasoning.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from core.enums import RuleType
from utils.owl_utils import get_owl_prop

logger = logging.getLogger(__name__)


class BaseAccessPostProcessor:
    """Добавляет или заменяет поля в словаре данных об элементе после reasoning."""

    def process(self, element_node: Any, current_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class DateWindowPostProcessor(BaseAccessPostProcessor):
    """Выкладывает valid_from / valid_until из date_restricted-политик в словарь ответа."""

    def process(self, element_node: Any, current_data: Dict[str, Any]) -> Dict[str, Any]:
        from_date = None
        until_date = None

        for policy in getattr(element_node, "has_access_policy", []) or []:
            if get_owl_prop(policy, "is_active", True) is False:
                continue
            if get_owl_prop(policy, "rule_type") != RuleType.DATE.value:
                continue
            from_date = _to_iso(get_owl_prop(policy, "valid_from"))
            until_date = _to_iso(get_owl_prop(policy, "valid_until"))

        if from_date:
            current_data["valid_from"] = from_date
        if until_date:
            current_data["valid_until"] = until_date
        return current_data


class BaseAccessFilter:
    """Проверяет элемент на допустимость при чтении из кэша."""

    def is_valid(self, element_data: Dict[str, Any]) -> bool:
        raise NotImplementedError


class DateWindowFilter(BaseAccessFilter):
    """Временное окно: элемент виден только между valid_from и valid_until."""

    def is_valid(self, element_data: Dict[str, Any]) -> bool:
        now = datetime.now(timezone.utc)
        from_dt = _parse_date(element_data.get("valid_from"))
        until_dt = _parse_date(element_data.get("valid_until"))
        if from_dt and now < from_dt:
            return False
        if until_dt and now > until_dt:
            return False
        return True


def _to_iso(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _parse_date(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as exc:
        logger.warning("Не удалось распарсить дату %r: %s", raw, exc)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
