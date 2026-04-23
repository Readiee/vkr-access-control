"""Тонкая обёртка над Owlready2: загрузка/сохранение OWL + репозитории ABox.

По DSL §44 OntologyCore отвечает за I/O онтологии и операции TBox/ABox. Кэш,
reasoning и graph-анализ — отдельные Core-компоненты, инжектятся через
`api/dependencies.py`. Репозитории (Student/Course/Progress/Policy) остаются
внутри OntologyCore, потому что они по сути — типизированные вьюхи над ABox
и не являются самостоятельными DSL-компонентами.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import redis
from owlready2 import World, default_world, get_ontology  # noqa: F401

from repositories.ontology_repositories import (
    CourseRepository,
    PolicyRepository,
    ProgressRepository,
    StudentRepository,
)

logger = logging.getLogger(__name__)


class OntologyCore:
    """Управляет загрузкой/сохранением онтологии и доступом к ABox через репозитории."""

    def __init__(self, onto_path: Optional[str] = None, world: Optional[World] = None) -> None:
        from core.config import DEFAULT_ONTOLOGY_PATH

        if onto_path is None:
            onto_path = DEFAULT_ONTOLOGY_PATH

        self.onto_file: str = onto_path
        logger.info("Загрузка онтологии из %s...", onto_path)
        self.world: World = world or default_world
        self.onto = self.world.get_ontology(onto_path).load()
        logger.info("Онтология успешно загружена.")

        self.students = StudentRepository(self.onto)
        self.courses = CourseRepository(self.onto)
        self.progress = ProgressRepository(self.onto)
        self.policies = PolicyRepository(self.onto)

    def save(self) -> None:
        """Сохраняет текущее состояние онтологии в файл."""
        self.onto.save(file=self.onto_file)

    def _get_node_label(self, node_id: str) -> str:
        """Возвращает человекочитаемое название OWL-индивида (по rdfs:label) или сам ID."""
        el = self.onto.search_one(iri=f"*{node_id}")
        if el and hasattr(el, "label") and el.label:
            return el.label[0]
        return node_id

    def _get_or_create_element(self, element_id: str, element_class: Any) -> Any:
        """Находит OWL-индивид по ID или создаёт новый.

        Поиск ограничен переданным классом, иначе суффикс `*element_id` может
        матчить индивид другого класса с тем же хвостом IRI.
        """
        element = self.onto.search_one(type=element_class, iri=f"*{element_id}")
        if not element:
            element = element_class(element_id)
        return element


def connect_redis(redis_url: str) -> Optional[redis.Redis]:
    """Подключение к Redis по URL. None при недоступности — кэширование становится no-op."""
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        logger.info("Подключение к Redis установлено.")
        return client
    except redis.ConnectionError:
        logger.warning("Redis недоступен — кэширование доступов отключено.")
        return None
