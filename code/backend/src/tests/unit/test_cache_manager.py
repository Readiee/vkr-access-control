"""Unit-тесты CacheManager: ontology_version, SCAN-инвалидация, startup-hook.

Используется fakeredis — REDIS_URL не нужен, тест не зависит от внешней инфраструктуры.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import fakeredis  # noqa: E402

from services.cache_manager import (  # noqa: E402
    ACCESS_KEY_PREFIX,
    CacheManager,
    ONTO_VERSION_KEY,
    VERIFY_KEY_PREFIX,
)


def _tmp_file(content: bytes = b"onto-v1") -> str:
    fd, path = tempfile.mkstemp(suffix=".owl", prefix="cachemgr_")
    os.close(fd)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


class CacheManagerVersionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.onto_path = _tmp_file(b"onto-v1")
        self.cache = CacheManager(self.redis, onto_path=self.onto_path)

    def tearDown(self) -> None:
        try:
            os.remove(self.onto_path)
        except OSError:
            pass

    def test_current_version_is_sha256_of_file(self) -> None:
        version = self.cache.current_ontology_version()

        self.assertIsNotNone(version)
        self.assertEqual(len(version), 64)  # sha256 hex

    def test_current_version_cached_by_mtime(self) -> None:
        first = self.cache.current_ontology_version()
        second = self.cache.current_ontology_version()

        self.assertIs(first, second)

    def test_current_version_recomputes_on_mtime_change(self) -> None:
        first = self.cache.current_ontology_version()

        time.sleep(0.05)
        with open(self.onto_path, "wb") as fh:
            fh.write(b"onto-v2")
        os.utime(self.onto_path, None)

        second = self.cache.current_ontology_version()
        self.assertNotEqual(first, second)

    def test_current_version_none_without_path(self) -> None:
        cache = CacheManager(self.redis, onto_path=None)

        self.assertIsNone(cache.current_ontology_version())


class CacheManagerAccessTests(unittest.TestCase):

    def setUp(self) -> None:
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.onto_path = _tmp_file(b"onto-v1")
        self.cache = CacheManager(self.redis, onto_path=self.onto_path)

    def tearDown(self) -> None:
        try:
            os.remove(self.onto_path)
        except OSError:
            pass

    def test_set_then_get_returns_access_map_without_service_fields(self) -> None:
        self.cache.set_student_access("student_1", {"elem_a": {}, "elem_b": {"foo": 1}})

        cached = self.cache.get_student_access("student_1")

        self.assertEqual(set(cached.keys()), {"elem_a", "elem_b"})
        self.assertEqual(cached["elem_b"], {"foo": 1})

    def test_get_miss_on_ontology_version_mismatch(self) -> None:
        self.cache.set_student_access("student_1", {"elem_a": {}})

        time.sleep(0.05)
        with open(self.onto_path, "wb") as fh:
            fh.write(b"onto-v2")
        os.utime(self.onto_path, None)
        self.cache._cached_version = None  # force recompute

        cached = self.cache.get_student_access("student_1")

        self.assertIsNone(cached)
        self.assertIsNone(self.redis.get(f"{ACCESS_KEY_PREFIX}student_1"))

    def test_get_legacy_payload_without_version_still_works(self) -> None:
        # Прежний формат (до введения ontology_version) тоже должен читаться.
        self.redis.set(
            f"{ACCESS_KEY_PREFIX}student_legacy",
            '{"elem_a": {}, "elem_b": {}}',
        )

        cached = self.cache.get_student_access("student_legacy")

        self.assertEqual(set(cached.keys()), {"elem_a", "elem_b"})

    def test_set_student_access_applies_ttl(self) -> None:
        self.cache.set_student_access("student_1", {"elem_a": {}})

        ttl = self.redis.ttl(f"{ACCESS_KEY_PREFIX}student_1")

        self.assertGreater(ttl, 3500)
        self.assertLessEqual(ttl, 3600)


class CacheManagerVerificationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.onto_path = _tmp_file()
        self.cache = CacheManager(self.redis, onto_path=self.onto_path)

    def tearDown(self) -> None:
        try:
            os.remove(self.onto_path)
        except OSError:
            pass

    def test_set_then_get_returns_same_payload(self) -> None:
        report = {"course_id": "c1", "run_id": "r1", "properties": {}}

        self.cache.set_verification("c1", report)
        cached = self.cache.get_verification("c1")

        self.assertEqual(cached["course_id"], "c1")
        self.assertIn("ontology_version", cached)

    def test_get_miss_on_version_mismatch(self) -> None:
        self.cache.set_verification("c1", {"course_id": "c1"})

        time.sleep(0.05)
        with open(self.onto_path, "wb") as fh:
            fh.write(b"updated")
        os.utime(self.onto_path, None)
        self.cache._cached_version = None

        self.assertIsNone(self.cache.get_verification("c1"))


class CacheManagerInvalidateTests(unittest.TestCase):

    def setUp(self) -> None:
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.onto_path = _tmp_file()
        self.cache = CacheManager(self.redis, onto_path=self.onto_path)

    def tearDown(self) -> None:
        try:
            os.remove(self.onto_path)
        except OSError:
            pass

    def test_invalidate_all_access_removes_all_access_keys_via_scan(self) -> None:
        for i in range(1200):
            self.cache.set_student_access(f"s_{i}", {"e": {}})
        self.redis.set("other:key", "keep")  # не должен задеть

        self.cache.invalidate_all_access()

        remaining = list(self.redis.scan_iter(match=f"{ACCESS_KEY_PREFIX}*"))
        self.assertEqual(remaining, [])
        self.assertEqual(self.redis.get("other:key"), "keep")

    def test_invalidate_verification_scoped_by_course(self) -> None:
        self.cache.set_verification("c1", {"course_id": "c1"})
        self.cache.set_verification("c2", {"course_id": "c2"})

        self.cache.invalidate_verification("c1")

        self.assertIsNone(self.redis.get(f"{VERIFY_KEY_PREFIX}c1:latest"))
        self.assertIsNotNone(self.redis.get(f"{VERIFY_KEY_PREFIX}c2:latest"))

    def test_invalidate_verification_all_when_no_course(self) -> None:
        self.cache.set_verification("c1", {"course_id": "c1"})
        self.cache.set_verification("c2", {"course_id": "c2"})

        self.cache.invalidate_verification()

        remaining = list(self.redis.scan_iter(match=f"{VERIFY_KEY_PREFIX}*"))
        self.assertEqual(remaining, [])


class CacheManagerStartupHookTests(unittest.TestCase):

    def setUp(self) -> None:
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.onto_path = _tmp_file(b"onto-v1")
        self.cache = CacheManager(self.redis, onto_path=self.onto_path)

    def tearDown(self) -> None:
        try:
            os.remove(self.onto_path)
        except OSError:
            pass

    def test_publish_writes_current_version_to_redis(self) -> None:
        version = self.cache.publish_ontology_version()

        self.assertEqual(self.redis.get(ONTO_VERSION_KEY), version)

    def test_ensure_consistency_noop_on_match(self) -> None:
        self.cache.publish_ontology_version()
        self.cache.set_student_access("s_1", {"e": {}})

        matched = self.cache.ensure_version_consistency()

        self.assertTrue(matched)
        self.assertIsNotNone(self.redis.get(f"{ACCESS_KEY_PREFIX}s_1"))

    def test_ensure_consistency_flushes_on_mismatch(self) -> None:
        self.cache.publish_ontology_version()
        self.cache.set_student_access("s_1", {"e": {}})
        self.cache.set_verification("c1", {"course_id": "c1"})

        # Подменяем версию в Redis — имитируем изменение файла между рестартами.
        self.redis.set(ONTO_VERSION_KEY, "stale-hash")

        matched = self.cache.ensure_version_consistency()

        self.assertFalse(matched)
        self.assertIsNone(self.redis.get(f"{ACCESS_KEY_PREFIX}s_1"))
        self.assertIsNone(self.redis.get(f"{VERIFY_KEY_PREFIX}c1:latest"))
        self.assertEqual(self.redis.get(ONTO_VERSION_KEY), self.cache.current_ontology_version())

    def test_no_redis_no_effect(self) -> None:
        cache = CacheManager(None, onto_path=self.onto_path)

        # Ни один метод не должен падать без Redis. publish возвращает версию файла,
        # но в Redis ничего не пишет (писать некуда).
        version = cache.publish_ontology_version()
        self.assertEqual(version, cache.current_ontology_version())
        self.assertTrue(cache.ensure_version_consistency())
        self.assertIsNone(cache.get_student_access("s_1"))
        cache.set_student_access("s_1", {"e": {}})
        cache.invalidate_all_access()
        cache.invalidate_verification()
        self.assertIsNone(cache.stored_ontology_version())


if __name__ == "__main__":
    unittest.main()
