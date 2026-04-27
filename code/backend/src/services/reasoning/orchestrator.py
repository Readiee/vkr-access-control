"""Единая точка запуска DL-резонера

Пайплайн: pre-enrich → Pellet + SWRL → подсчёт выводов

Pre-enrich чистит старые satisfies/is_available_for и подкладывает индивиды,
которые SWRL не может вычислить сам — текущее время и агрегаты оценок. Таймаут
прогона нужен, чтобы HTTP-запрос не висел бесконечно на сложной онтологии

Default-deny при отсутствии вывода и материализация в Redis — ответственность
AccessService на чтении, не этого модуля
"""
from __future__ import annotations

import logging
import subprocess
import threading
from dataclasses import dataclass
from typing import Any, Optional

from owlready2 import sync_reasoner_pellet

from services.reasoning._enricher import (
    clear_inferred_triples,
    enrich_aggregates,
    enrich_current_time,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 10  # дальше синхронный HTTP-запрос теряет смысл
_PELLET_PATCH_LOCK = threading.Lock()


@dataclass
class ReasoningResult:
    status: str  # "ok" | "timeout" | "inconsistent" | "error"
    duration_sec: float = 0.0
    aggregate_facts: int = 0
    satisfies_count: int = 0
    available_count: int = 0
    error: Optional[str] = None
    timed_out: bool = False


class ReasoningTimeoutError(Exception):
    """Pellet не уложился в заданный таймаут"""


class ReasoningOrchestrator:
    """Единая точка вызова резонера; сервисы зовут её вместо sync_reasoner_pellet напрямую"""

    def __init__(self, onto: Any, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> None:
        self.onto = onto
        self.timeout_sec = timeout_sec

    def reason(self) -> ReasoningResult:
        import time
        started = time.monotonic()

        try:
            clear_inferred_triples(self.onto)
            enrich_current_time(self.onto)
            agg_count = enrich_aggregates(self.onto)
        except Exception as exc:
            logger.exception("pre-enrich упал")
            return ReasoningResult(status="error", error=f"pre_enrich: {exc}")

        try:
            self._run_pellet_with_timeout()
        except ReasoningTimeoutError:
            logger.warning("Pellet не уложился в %.1fs", self.timeout_sec)
            return ReasoningResult(
                status="timeout",
                duration_sec=time.monotonic() - started,
                aggregate_facts=agg_count,
                timed_out=True,
            )
        except Exception as exc:
            msg = str(exc)
            if "inconsistent" in msg.lower() or "InconsistentOntologyError" in msg:
                logger.warning("Онтология inconsistent: %s", msg)
                return ReasoningResult(status="inconsistent", error=msg,
                                       duration_sec=time.monotonic() - started)
            logger.exception("Pellet упал")
            return ReasoningResult(status="error", error=msg,
                                   duration_sec=time.monotonic() - started)

        satisfies_count = sum(
            len(getattr(s, "satisfies", []) or [])
            for s in self.onto.Student.instances()
        )
        available_count = sum(
            len(getattr(e, "is_available_for", []) or [])
            for e in self.onto.CourseStructure.instances()
        )

        return ReasoningResult(
            status="ok",
            duration_sec=time.monotonic() - started,
            aggregate_facts=agg_count,
            satisfies_count=satisfies_count,
            available_count=available_count,
        )

    def check_consistency(self) -> tuple[bool, Optional[str]]:
        """Прогнать резонер и вернуть (consistent, explanation)

        При ok — (True, None). При inconsistent — (False, сообщение резонера).
        Таймаут и ошибки трактуются как «нельзя утверждать, что consistent»
        """
        result = self.reason()
        if result.status == "inconsistent":
            return False, result.error
        if result.status == "ok":
            return True, None
        return False, result.error or result.status

    def _run_pellet_with_timeout(self) -> None:
        """Запустить sync_reasoner_pellet с патчем Jena→OWLAPI и таймаутом"""
        error_holder: list[BaseException] = []

        def target() -> None:
            try:
                self._patched_sync_reasoner()
            except BaseException as exc:
                error_holder.append(exc)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout_sec)

        if thread.is_alive():
            # Pellet крутится в java-подпроцессе, отдельный поток его не прервёт;
            # отдаём таймаут вызывающему, подпроцесс завершится сам
            raise ReasoningTimeoutError(
                f"Pellet не завершился за {self.timeout_sec}s"
            )
        if error_holder:
            raise error_holder[0]

    def _patched_sync_reasoner(self) -> None:
        """Подменить Jena-loader на OWLAPI в команде запуска Pellet"""
        with _PELLET_PATCH_LOCK:
            original_run = subprocess.run

            def patched_run(cmd, *args, **kwargs):
                if isinstance(cmd, list) and "java" in cmd and "Jena" in cmd:
                    cmd[cmd.index("Jena")] = "OWLAPI"
                return original_run(cmd, *args, **kwargs)

            subprocess.run = patched_run
            try:
                # Первый аргумент — онтология/мир; без него Pellet берёт default_world
                # и пропускает индивидов из изолированных World (тесты, многопоточка)
                sync_reasoner_pellet(
                    self.onto.world,
                    infer_property_values=True,
                    infer_data_property_values=True,
                )
            finally:
                subprocess.run = original_run
