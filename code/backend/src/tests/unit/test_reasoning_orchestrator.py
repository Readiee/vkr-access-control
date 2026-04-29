"""Unit-тесты ReasoningOrchestrator: process-wide лок сериализует reason()

Pellet и pre-enrich мокаются; проверяется, что параллельные reason() не
пересекаются по времени, потому что общий World и subprocess.run-патч
не выдерживают одновременного выполнения
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from typing import List, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from owlready2 import World

from core.config import DEFAULT_ONTOLOGY_PATH
from services.reasoning import orchestrator as orch_module
from services.reasoning.orchestrator import ReasoningOrchestrator


class ReasoningLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.onto = self.world.get_ontology(DEFAULT_ONTOLOGY_PATH).load()
        self.orchestrator = ReasoningOrchestrator(self.onto)

        # snapshot оригинальных функций модуля для tearDown
        self._orig_pellet = orch_module.sync_reasoner_pellet
        self._orig_clear = orch_module.clear_inferred_triples
        self._orig_time = orch_module.enrich_current_time
        self._orig_agg = orch_module.enrich_aggregates

    def tearDown(self) -> None:
        orch_module.sync_reasoner_pellet = self._orig_pellet
        orch_module.clear_inferred_triples = self._orig_clear
        orch_module.enrich_current_time = self._orig_time
        orch_module.enrich_aggregates = self._orig_agg
        self.world.close()

    def test_concurrent_reason_calls_serialize_through_lock(self):
        """Два потока reason() не пересекаются по времени работы Pellet

        Замок оборачивает весь reason() (pre-enrich + Pellet). Проверка по
        интервалам [t_in, t_out] фейкового Pellet: интервалы не должны
        перекрываться. Порядок не важен — важна сериализация
        """
        intervals: List[Tuple[float, float]] = []
        intervals_lock = threading.Lock()
        sleep_sec = 0.2

        def fake_pellet(*args, **kwargs):
            t_in = time.monotonic()
            time.sleep(sleep_sec)
            t_out = time.monotonic()
            with intervals_lock:
                intervals.append((t_in, t_out))

        orch_module.sync_reasoner_pellet = fake_pellet
        orch_module.clear_inferred_triples = lambda onto: None
        orch_module.enrich_current_time = lambda onto, now=None: None
        orch_module.enrich_aggregates = lambda onto: 0

        results: List = []
        results_lock = threading.Lock()

        def runner():
            r = self.orchestrator.reason()
            with results_lock:
                results.append(r)

        t1 = threading.Thread(target=runner)
        t2 = threading.Thread(target=runner)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertFalse(t1.is_alive(), "поток 1 не завершился — возможен deadlock")
        self.assertFalse(t2.is_alive(), "поток 2 не завершился — возможен deadlock")
        self.assertEqual(len(intervals), 2)
        self.assertEqual(len(results), 2)

        first, second = sorted(intervals, key=lambda iv: iv[0])
        self.assertGreaterEqual(
            second[0], first[1] - 1e-3,
            f"интервалы Pellet перекрываются: {first} vs {second}",
        )
        for r in results:
            self.assertEqual(r.status, "ok")


if __name__ == "__main__":
    unittest.main()
