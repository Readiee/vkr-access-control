"""Единая точка запуска DL-резонера: pre-enrich, Pellet, подсчёт выводов.

Pre-enrich чистит старые satisfies/is_available_for и подкладывает индивиды,
которых SWRL не знает: текущее время и агрегаты оценок. Default-deny остаётся
за AccessService при чтении.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from owlready2 import sync_reasoner_pellet

from core.enums import ReasoningStatus
from services.reasoning._enricher import (
    clear_inferred_triples,
    enrich_aggregates,
    enrich_current_time,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 10  # дальше синхронный HTTP-запрос теряет смысл

# pre-enrich и sync_reasoner_pellet работают на общий World; без сериализации
# параллельные прогоны затрут друг друга в ABox
_REASON_LOCK = threading.Lock()

_INCONSISTENT_MARKERS = ("inconsistent", "InconsistentOntologyError")


@dataclass
class ReasoningResult:
    status: str
    duration_sec: float = 0.0
    aggregate_facts: int = 0
    satisfies_count: int = 0
    available_count: int = 0
    error: Optional[str] = None
    timed_out: bool = False


class ReasoningTimeoutError(Exception):
    """Pellet не уложился в заданный таймаут."""


class ReasoningOrchestrator:
    def __init__(self, onto: Any, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> None:
        self.onto = onto
        self.timeout_sec = timeout_sec

    def reason(self) -> ReasoningResult:
        with _REASON_LOCK:
            return self._reason_locked()

    def _reason_locked(self) -> ReasoningResult:
        started = time.monotonic()

        try:
            clear_inferred_triples(self.onto)
            enrich_current_time(self.onto)
            agg_count = enrich_aggregates(self.onto)
        except Exception as exc:
            logger.exception("pre-enrich упал")
            return ReasoningResult(status=ReasoningStatus.ERROR.value, error=f"pre_enrich: {exc}")

        try:
            self._run_pellet_with_timeout()
        except ReasoningTimeoutError:
            logger.warning("Pellet не уложился в %.1fs", self.timeout_sec)
            return ReasoningResult(
                status=ReasoningStatus.TIMEOUT.value,
                duration_sec=time.monotonic() - started,
                aggregate_facts=agg_count,
                timed_out=True,
            )
        except Exception as exc:
            msg = str(exc)
            if any(marker.lower() in msg.lower() for marker in _INCONSISTENT_MARKERS):
                logger.warning("Онтология inconsistent: %s", msg)
                return ReasoningResult(
                    status=ReasoningStatus.INCONSISTENT.value, error=msg,
                    duration_sec=time.monotonic() - started,
                )
            logger.exception("Pellet упал")
            return ReasoningResult(
                status=ReasoningStatus.ERROR.value, error=msg,
                duration_sec=time.monotonic() - started,
            )

        satisfies_count = sum(
            len(getattr(s, "satisfies", []) or [])
            for s in self.onto.Student.instances()
        )
        available_count = sum(
            len(getattr(e, "is_available_for", []) or [])
            for e in self.onto.CourseStructure.instances()
        )

        return ReasoningResult(
            status=ReasoningStatus.OK.value,
            duration_sec=time.monotonic() - started,
            aggregate_facts=agg_count,
            satisfies_count=satisfies_count,
            available_count=available_count,
        )

    def check_consistency(self) -> tuple[bool, Optional[str]]:
        """(consistent, explanation): timeout/error трактуются как «не-consistent»."""
        result = self.reason()
        if result.status == ReasoningStatus.INCONSISTENT.value:
            return False, result.error
        if result.status == ReasoningStatus.OK.value:
            return True, None
        return False, result.error or result.status

    def _run_pellet_with_timeout(self) -> None:
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
            # Pellet крутится в java-подпроцессе; thread.join не убьёт его —
            # отдадим таймаут наверх, java-процесс отработает и закроется сам
            raise ReasoningTimeoutError(f"Pellet не завершился за {self.timeout_sec}s")
        if error_holder:
            raise error_holder[0]

    def _patched_sync_reasoner(self) -> None:
        """sync_reasoner_pellet с подменой Jena-loader на OWLAPI в команде запуска."""
        original_run = subprocess.run

        def patched_run(cmd, *args, **kwargs):
            if isinstance(cmd, list) and "java" in cmd and "Jena" in cmd:
                cmd[cmd.index("Jena")] = "OWLAPI"
            return original_run(cmd, *args, **kwargs)

        subprocess.run = patched_run
        try:
            # явный world обязателен: иначе Pellet берёт default_world и теряет
            # индивидов в изолированных World — это особенно бьёт по тестам
            sync_reasoner_pellet(
                self.onto.world,
                infer_property_values=True,
                infer_data_property_values=True,
            )
        finally:
            subprocess.run = original_run
