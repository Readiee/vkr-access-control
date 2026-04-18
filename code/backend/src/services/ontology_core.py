import logging
import subprocess
import redis
from typing import Optional, Any
from owlready2 import get_ontology, sync_reasoner_pellet
from repositories.ontology_repositories import StudentRepository, CourseRepository, ProgressRepository, PolicyRepository
from services.cache_service import CacheService

logger = logging.getLogger(__name__)

class OntologyCore:
    """Управляет операциями с семантическим графом, ризонером и кэшем Redis."""

    def __init__(self, onto_path: str = "data/edu_ontology_with_rules.owl") -> None:
        """Загружает онтологию в память и подключается к Redis."""
        self.onto_file: str = onto_path
        logger.info("Загрузка онтологии из %s...", onto_path)
        self.onto = get_ontology(onto_path).load()
        logger.info("Онтология успешно загружена.")
        self.redis_client: Optional[redis.Redis] = self._connect_redis()
        
        # Инициализация сервисов и репозиториев
        self.cache = CacheService(self.redis_client)
        self.students = StudentRepository(self.onto)
        self.courses = CourseRepository(self.onto)
        self.progress = ProgressRepository(self.onto)
        self.policies = PolicyRepository(self.onto)


    def _connect_redis(self) -> Optional[redis.Redis]:
        """Устанавливает соединение с Redis. Возвращает None при недоступности."""
        try:
            client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
            client.ping()
            logger.info("Подключение к Redis установлено.")
            return client
        except redis.ConnectionError:
            logger.warning("Redis недоступен — кэширование доступов отключено.")
            return None

    def run_reasoner(self) -> None:
        """Запускает Pellet Reasoner с патчем совместимости Java/Jena."""
        original_run = subprocess.run

        def patched_run(cmd, *args, **kwargs):
            if isinstance(cmd, list) and "java" in cmd and "Jena" in cmd:
                cmd[cmd.index("Jena")] = "OWLAPI"
            return original_run(cmd, *args, **kwargs)

        subprocess.run = patched_run
        try:
            sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        finally:
            subprocess.run = original_run

    def save(self):
        """Сохраняет текущее состояние онтологии в файл."""
        self.onto.save(file=self.onto_file)

    def _get_node_label(self, node_id: str) -> str:
        """Возвращает человекочитаемое название OWL-индивида (по rdfs:label) или сам ID."""
        el = self.onto.search_one(iri=f"*{node_id}")
        if el and hasattr(el, "label") and el.label:
            return el.label[0]
        return node_id

    def _get_or_create_element(self, element_id: str, element_class: Any) -> Any:
        """Находит OWL-индивид по ID или создаёт новый."""
        element = self.onto.search_one(iri=f"*{element_id}")
        if not element:
            element = element_class(element_id)
        return element


