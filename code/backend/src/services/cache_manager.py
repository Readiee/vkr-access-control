from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

STUDENT_ACCESS_TTL_SECONDS = 3600
VERIFICATION_TTL_SECONDS = 3600

ONTO_VERSION_KEY = "onto:version"
ACCESS_KEY_PREFIX = "access:"
VERIFY_KEY_PREFIX = "verify:"
_SCAN_BATCH = 500


class CacheManager:
    """Кэш решений о доступе и отчётов верификации. GET/SET/DEL + инвалидация затронутых ключей (А5).

    TTL фиксирован на 1 час для всех ключей. Методист задаёт date_restricted-окна
    с шагом ровно 1 час (схема валидирует это), поэтому кэш гарантированно
    пересчитается до следующей границы — без отдельного cron-воркера и адаптивного TTL.

    Payload `access:{s}` и `verify:{c}:latest` хранят `ontology_version` — sha256
    файла онтологии на момент записи. При GET значения с чужой версией
    считаются stale и выбрасываются с cache-miss. Wildcard-инвалидация идёт
    через `SCAN` батчами, не `KEYS` (последний блокирует Redis при большом
    количестве ключей).
    """

    def __init__(self, redis_client, onto_path: Optional[str] = None) -> None:
        self.redis = redis_client
        self._onto_path = onto_path
        self._cached_version: Optional[str] = None
        self._cached_mtime: Optional[float] = None

    # ------------------------------------------------------------------
    # Ontology version
    # ------------------------------------------------------------------
    def current_ontology_version(self) -> Optional[str]:
        """sha256 содержимого файла онтологии. None, если путь не задан или файл отсутствует.

        Пересчёт на изменение mtime, иначе возвращается закэшированный хэш.
        """
        if not self._onto_path:
            return None
        try:
            mtime = os.path.getmtime(self._onto_path)
        except OSError:
            return None
        if self._cached_version is not None and self._cached_mtime == mtime:
            return self._cached_version

        digest = hashlib.sha256()
        try:
            with open(self._onto_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    digest.update(chunk)
        except OSError as exc:
            logger.warning("Не удалось прочитать онтологию для версии: %s", exc)
            return None
        self._cached_version = digest.hexdigest()
        self._cached_mtime = mtime
        return self._cached_version

    def publish_ontology_version(self) -> Optional[str]:
        """Положить текущий хэш онтологии в `onto:version`. Возвращает записанное значение."""
        version = self.current_ontology_version()
        if self.redis and version:
            try:
                self.redis.set(ONTO_VERSION_KEY, version)
            except Exception as exc:
                logger.warning("Ошибка публикации onto:version: %s", exc)
        return version

    def stored_ontology_version(self) -> Optional[str]:
        """Прочитать `onto:version` из Redis. None, если нет значения или Redis недоступен."""
        if not self.redis:
            return None
        try:
            return self.redis.get(ONTO_VERSION_KEY)
        except Exception as exc:
            logger.warning("Ошибка чтения onto:version: %s", exc)
            return None

    def ensure_version_consistency(self) -> bool:
        """Startup-hook: при рассинхроне стертого хэша онтологии вычищает access:* и verify:*.

        Возвращает True, если версия совпала (или Redis недоступен, или файл не задан),
        False — если потребовалась инвалидация.
        """
        current = self.current_ontology_version()
        if not current or not self.redis:
            return True
        stored = self.stored_ontology_version()
        if stored == current:
            return True
        logger.warning(
            "Версия онтологии изменилась (%s → %s). Инвалидация access:* и verify:*.",
            stored or "∅", current[:12],
        )
        self.invalidate_all_access()
        self.invalidate_verification()
        self.publish_ontology_version()
        return False

    # ------------------------------------------------------------------
    # Access cache
    # ------------------------------------------------------------------
    def get_student_access(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Вернуть access-map студента или None при miss.

        Служебные поля (`ontology_version`) обёрнуты внутри payload и наружу не видны —
        сервисы продолжают видеть тот же dict element_id → meta, что и до обогащения.
        """
        if not self.redis:
            return None
        raw = self.redis.get(f"{ACCESS_KEY_PREFIX}{student_id}")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not self._version_matches(payload):
            self._safe_delete(f"{ACCESS_KEY_PREFIX}{student_id}")
            return None
        if isinstance(payload, dict) and "access" in payload:
            return payload.get("access") or {}
        # legacy-payload без обёртки — считаем валидным
        return payload

    def set_student_access(self, student_id: str, data: Dict[str, Any]) -> None:
        if not self.redis:
            return
        access_map = dict(data) if isinstance(data, dict) else {}
        payload: Dict[str, Any] = {"access": access_map}
        version = self.current_ontology_version()
        if version:
            payload["ontology_version"] = version
        try:
            self.redis.set(
                f"{ACCESS_KEY_PREFIX}{student_id}",
                json.dumps(payload, default=str),
                ex=STUDENT_ACCESS_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("Ошибка записи access:%s — %s", student_id, exc)
            return
        logger.info("Доступы для %s сохранены в Redis.", student_id)

    def invalidate_all_access(self) -> None:
        self._scan_and_delete(f"{ACCESS_KEY_PREFIX}*", label="доступов")

    # ------------------------------------------------------------------
    # Verification cache (UC-6)
    # ------------------------------------------------------------------
    def get_verification(self, course_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        raw = self.redis.get(f"{VERIFY_KEY_PREFIX}{course_id}:latest")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not self._version_matches(payload):
            self._safe_delete(f"{VERIFY_KEY_PREFIX}{course_id}:latest")
            return None
        return payload

    def set_verification(self, course_id: str, report: Dict[str, Any]) -> None:
        if not self.redis:
            return
        payload = dict(report) if isinstance(report, dict) else {"value": report}
        version = self.current_ontology_version()
        if version:
            payload.setdefault("ontology_version", version)
        try:
            self.redis.set(
                f"{VERIFY_KEY_PREFIX}{course_id}:latest",
                json.dumps(payload, default=str),
                ex=VERIFICATION_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("Ошибка записи verify:%s — %s", course_id, exc)

    def invalidate_verification(self, course_id: Optional[str] = None) -> None:
        pattern = f"{VERIFY_KEY_PREFIX}{course_id}:*" if course_id else f"{VERIFY_KEY_PREFIX}*"
        self._scan_and_delete(pattern, label="верификации")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _scan_and_delete(self, pattern: str, *, label: str) -> None:
        if not self.redis:
            return
        try:
            # SCAN под параллельным удалением пропускает часть ключей (курсор сдвигается
            # на удалённых слотах), поэтому материализуем список до первого DEL.
            keys = list(self._scan_iter(pattern))
            if not keys:
                return
            for i in range(0, len(keys), _SCAN_BATCH):
                self.redis.delete(*keys[i:i + _SCAN_BATCH])
            logger.info("Сброс кэша %s: удалено %d ключей (pattern=%s).", label, len(keys), pattern)
        except Exception as exc:
            logger.error("Ошибка при SCAN-инвалидации %s: %s", pattern, exc)

    def _scan_iter(self, pattern: str) -> Iterable[str]:
        # Отдельная обёртка над scan_iter — совместима с redis-py и fakeredis.
        yield from self.redis.scan_iter(match=pattern, count=_SCAN_BATCH)

    def _safe_delete(self, key: str) -> None:
        if not self.redis:
            return
        try:
            self.redis.delete(key)
        except Exception as exc:
            logger.warning("Ошибка удаления %s: %s", key, exc)

    def _version_matches(self, payload: Any) -> bool:
        """Совпадает ли `ontology_version` в payload с текущим хэшом файла.

        True при: хэш файла недоступен; payload не содержит поля; значения совпадают.
        False только при явном расхождении.
        """
        current = self.current_ontology_version()
        if not current or not isinstance(payload, dict):
            return True
        cached = payload.get("ontology_version")
        return cached is None or cached == current
