"""Обёртка над Moodle Web Services REST API.

Тонкий клиент с типизированными методами под endpoint-ы, нужные для импорта
структуры курса. Аутентификация — через токен пользователя с правами
`webservice/rest:use` и доступом к функциям ниже. Создание токена и настройка
ролей описаны в README.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests


_DEFAULT_TIMEOUT = 10.0


class MoodleAPIError(RuntimeError):
    """Ошибка вызова Moodle Web Services."""


@dataclass
class MoodleClient:
    """Клиент Moodle Web Services."""

    base_url: str
    token: str
    timeout: float = _DEFAULT_TIMEOUT

    def _call(self, function: str, **params: Any) -> Any:
        url = f"{self.base_url.rstrip('/')}/webservice/rest/server.php"
        payload: Dict[str, Any] = {
            "wstoken": self.token,
            "moodlewsrestformat": "json",
            "wsfunction": function,
        }
        # Moodle принимает параметры со скобочной нотацией: criteria[0][key]=...
        # requests при передаче словарей с tuple-ключами корректно их кодирует.
        flat = _flatten(params)
        payload.update(flat)
        response = requests.post(url, data=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        if isinstance(body, dict) and body.get("exception"):
            raise MoodleAPIError(f"{function}: {body.get('message')}")
        return body

    def get_course_by_shortname(self, shortname: str) -> Dict[str, Any]:
        result = self._call(
            "core_course_get_courses_by_field",
            field="shortname",
            value=shortname,
        )
        courses = result.get("courses") or []
        if not courses:
            raise MoodleAPIError(f"Курс с shortname={shortname!r} не найден")
        return courses[0]

    def get_course_contents(self, course_id: int) -> List[Dict[str, Any]]:
        return self._call("core_course_get_contents", courseid=course_id)

    def get_enrolled_users(self, course_id: int) -> List[Dict[str, Any]]:
        return self._call("core_enrol_get_enrolled_users", courseid=course_id)

    def get_course_groups(self, course_id: int) -> List[Dict[str, Any]]:
        return self._call("core_group_get_course_groups", courseid=course_id)

    def get_group_members(self, group_ids: Iterable[int]) -> List[Dict[str, Any]]:
        ids = list(group_ids)
        if not ids:
            return []
        return self._call("core_group_get_group_members", groupids=ids)

    def get_grade_items(self, course_id: int) -> List[Dict[str, Any]]:
        return self._call("gradereport_user_get_grade_items", courseid=course_id)

    def get_course_competencies(self, course_id: int) -> List[Dict[str, Any]]:
        try:
            return self._call("core_competency_list_course_competencies", id=course_id)
        except MoodleAPIError:
            # Подсистема компетенций может быть выключена в инстансе.
            return []


def _flatten(params: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Привести вложенные dict/list к Moodle-нотации с квадратными скобками."""
    flat: Dict[str, Any] = {}
    for key, value in params.items():
        composite = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, composite))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                inner = f"{composite}[{index}]"
                if isinstance(item, (dict, list)):
                    flat.update(_flatten({index: item}, composite))
                else:
                    flat[inner] = item
        else:
            flat[composite] = value
    return flat
