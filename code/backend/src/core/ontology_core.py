"""Загрузка и сохранение OWL-онтологии плюс репозитории ABox."""
from __future__ import annotations

import logging
from typing import Any, Optional

import redis
from owlready2 import World, default_world

from repositories.ontology_repositories import (
    CourseRepository,
    PolicyRepository,
    ProgressRepository,
    StudentRepository,
)
from utils.owl_utils import label_or_name

logger = logging.getLogger(__name__)


class OntologyCore:
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
        self.onto.save(file=self.onto_file)

    def _get_node_label(self, node_id: str) -> str:
        el = self.onto.search_one(iri=f"*{node_id}")
        return label_or_name(el) if el is not None else node_id

    def _get_or_create_element(self, element_id: str, element_class: Any) -> Any:
        # Поиск ограничен переданным классом: суффикс `*element_id` без type=
        # матчит индивид другого класса с тем же хвостом IRI.
        element = self.onto.search_one(type=element_class, iri=f"*{element_id}")
        if not element:
            element = element_class(element_id)
        return element


def connect_redis(redis_url: str) -> Optional[redis.Redis]:
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        logger.info("Подключение к Redis установлено.")
        return client
    except redis.ConnectionError:
        logger.warning("Redis недоступен — кэширование доступов отключено.")
        return None
