import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, redis_client):
        self.redis = redis_client

    def get_student_access(self, student_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        data = self.redis.get(f"access:{student_id}")
        return json.loads(data) if data else None

    def set_student_access(self, student_id: str, data: Dict[str, Any]) -> None:
        if self.redis:
            self.redis.set(f"access:{student_id}", json.dumps(data))
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
            self.redis.set(f"verify:{course_id}:latest", json.dumps(report, default=str))

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
