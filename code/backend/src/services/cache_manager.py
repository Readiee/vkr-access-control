import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

STUDENT_ACCESS_TTL_SECONDS = 3600
VERIFICATION_TTL_SECONDS = 3600


class CacheManager:
    """Кэш решений о доступе и отчётов верификации. GET/SET/DEL + инвалидация затронутых ключей (А5).

    TTL фиксирован на 1 час для всех ключей. Методист задаёт date_restricted-окна
    с шагом ровно 1 час (схема валидирует это), поэтому кэш гарантированно
    пересчитается до следующей границы — без отдельного cron-воркера и адаптивного TTL.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    def get_student_access(self, student_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        data = self.redis.get(f"access:{student_id}")
        return json.loads(data) if data else None

    def set_student_access(self, student_id: str, data: Dict[str, Any]) -> None:
        if self.redis:
            self.redis.set(f"access:{student_id}", json.dumps(data), ex=STUDENT_ACCESS_TTL_SECONDS)
            logger.info("Доступы для %s сохранены в Redis.", student_id)

    def invalidate_all_access(self) -> None:
        if self.redis:
            try:
                keys = self.redis.keys("access:*")
                if keys:
                    self.redis.delete(*keys)
                    logger.info(f"Сброшен кэш доступов: удалено {len(keys)} ключей.")
            except Exception as e:
                logger.error(f"Ошибка при очистке кэша Redis: {e}")

    # ---- verification cache (UC-6) ----

    def get_verification(self, course_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        data = self.redis.get(f"verify:{course_id}:latest")
        return json.loads(data) if data else None

    def set_verification(self, course_id: str, report: Dict[str, Any]) -> None:
        if self.redis:
            self.redis.set(
                f"verify:{course_id}:latest",
                json.dumps(report, default=str),
                ex=VERIFICATION_TTL_SECONDS,
            )

    def invalidate_verification(self, course_id: Optional[str] = None) -> None:
        if not self.redis:
            return
        try:
            pattern = f"verify:{course_id}:*" if course_id else "verify:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                logger.info("Сброшен кэш верификации: %d ключей.", len(keys))
        except Exception as e:
            logger.error("Ошибка при инвалидации verify-кэша: %s", e)
