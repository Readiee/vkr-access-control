"""Замеры производительности: scalability и cache-hit/miss latency

Два независимых замера:
- scalability_run: verify на курсах с 10/50/100/500 политик, N прогонов на размер.
  Цель — тренд времени reasoning+verify по n_policies, сравнение с целевым
  значением задержки cache-miss
- latency_run: AccessService с fakeredis. Полный путь miss (reasoning + AccessService)
  и повторный hit (чтение из Redis). Сравнение с целевой задержкой cache-hit
"""
from __future__ import annotations

import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import fakeredis
from owlready2 import World

# Пути импорта подтягивает ноутбук; модуль не рассчитан на standalone-запуск
from services.ontology_core import OntologyCore
from services.cache_manager import CacheManager
from services.reasoning import ReasoningOrchestrator
from services.verification import VerificationService
from services.access.service import AccessService

from _common.generator import GenerationConfig, generate_scenario


@dataclass(frozen=True)
class ScalabilityPoint:
    n_policies: int
    run_index: int
    reason_ms: float
    verify_ms: float
    total_ms: float


@dataclass(frozen=True)
class LatencyPoint:
    mode: str           # "miss" или "hit"
    run_index: int
    latency_ms: float


SCALABILITY_SIZES = [
    (10,  2,  6),    # n_policies, n_modules, n_activities_per_module
    (50,  5, 11),
    (100, 10, 11),
    (500, 25, 21),
]


def scalability_run(output_dir: Path, repeats: int = 3) -> list[ScalabilityPoint]:
    results: list[ScalabilityPoint] = []
    for n_policies, n_modules, n_activities in SCALABILITY_SIZES:
        cfg = GenerationConfig(
            n_modules=n_modules,
            n_activities_per_module=n_activities,
            n_students=3,
            n_policies=n_policies,
            course_id=f"course_scale_{n_policies}",
        )
        owl_path = output_dir / f"scale_{n_policies:04d}.owl"
        generate_scenario(cfg, owl_path)

        for run_i in range(repeats):
            world = World()
            onto = world.get_ontology(f"file://{str(owl_path).replace(os.sep, '/')}").load()
            core = OntologyCore(onto_path=str(owl_path), world=world)
            core.onto = onto
            core.world = world
            reasoner = ReasoningOrchestrator(core.onto)
            service = VerificationService(core, reasoner=reasoner, cache=CacheManager(None))

            t0 = time.perf_counter()
            result = reasoner.reason()
            reason_ms = (time.perf_counter() - t0) * 1000.0
            if result.status != "ok":
                raise RuntimeError(f"Reasoner failed on n_policies={n_policies}: {result.status}")

            t0 = time.perf_counter()
            service.verify(cfg.course_id, include_subsumption=False)
            verify_ms = (time.perf_counter() - t0) * 1000.0

            results.append(ScalabilityPoint(
                n_policies=n_policies,
                run_index=run_i,
                reason_ms=reason_ms,
                verify_ms=verify_ms,
                total_ms=reason_ms + verify_ms,
            ))
    return results


def latency_run(output_dir: Path, *, warmup: int = 3, repeats: int = 30) -> list[LatencyPoint]:
    cfg = GenerationConfig(
        n_modules=5,
        n_activities_per_module=8,
        n_students=5,
        n_policies=30,
        course_id="course_latency_bench",
    )
    owl_path = output_dir / "latency_bench.owl"
    generate_scenario(cfg, owl_path)

    world = World()
    onto = world.get_ontology(f"file://{str(owl_path).replace(os.sep, '/')}").load()
    core = OntologyCore(onto_path=str(owl_path), world=world)
    core.onto = onto
    core.world = world
    reasoner = ReasoningOrchestrator(core.onto)
    reasoner.reason()

    points: list[LatencyPoint] = []
    student_id = "gen_student_0"

    # Warmup: несколько прогонов, чтобы JVM и Redis разогрелись
    for _ in range(warmup):
        cache = CacheManager(fakeredis.FakeRedis())
        access = AccessService(core, cache=cache, reasoner=reasoner)
        access.get_course_access(student_id, cfg.course_id)
        access.get_course_access(student_id, cfg.course_id)

    for run_i in range(repeats):
        # miss: свежий кэш, первый get_course_access пересчитывает и записывает
        cache = CacheManager(fakeredis.FakeRedis())
        access = AccessService(core, cache=cache, reasoner=reasoner)
        t0 = time.perf_counter()
        access.get_course_access(student_id, cfg.course_id)
        miss_ms = (time.perf_counter() - t0) * 1000.0
        points.append(LatencyPoint(mode="miss", run_index=run_i, latency_ms=miss_ms))

        # hit: повторный get_course_access читает из Redis
        t0 = time.perf_counter()
        access.get_course_access(student_id, cfg.course_id)
        hit_ms = (time.perf_counter() - t0) * 1000.0
        points.append(LatencyPoint(mode="hit", run_index=run_i, latency_ms=hit_ms))

    return points


def cold_miss_run(output_dir: Path, *, repeats: int = 5) -> list[LatencyPoint]:
    """Холодный старт: свежий world + reasoning + AccessService

    Замеряет полный путь от нуля до первого доступа. В production этот путь
    проходит при первом запуске backend или после инвалидации версии TBox
    """
    cfg = GenerationConfig(
        n_modules=5,
        n_activities_per_module=8,
        n_students=5,
        n_policies=30,
        course_id="course_cold_bench",
    )
    owl_path = output_dir / "cold_bench.owl"
    generate_scenario(cfg, owl_path)

    points: list[LatencyPoint] = []
    for run_i in range(repeats):
        t0 = time.perf_counter()
        world = World()
        onto = world.get_ontology(f"file://{str(owl_path).replace(os.sep, '/')}").load()
        core = OntologyCore(onto_path=str(owl_path), world=world)
        core.onto = onto
        core.world = world
        reasoner = ReasoningOrchestrator(core.onto)
        reasoner.reason()
        access = AccessService(core, cache=CacheManager(fakeredis.FakeRedis()), reasoner=reasoner)
        access.get_course_access("gen_student_0", cfg.course_id)
        cold_ms = (time.perf_counter() - t0) * 1000.0
        points.append(LatencyPoint(mode="cold_miss", run_index=run_i, latency_ms=cold_ms))
    return points


def summarize_latency(points: list[LatencyPoint]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    modes = sorted({p.mode for p in points})
    for mode in modes:
        values = [p.latency_ms for p in points if p.mode == mode]
        if not values:
            continue
        values_sorted = sorted(values)
        out[mode] = {
            "n": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": values_sorted[int(0.95 * (len(values) - 1))],
            "p99": values_sorted[int(0.99 * (len(values) - 1))],
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    return out


def summarize_scalability(points: list[ScalabilityPoint]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    sizes = sorted({p.n_policies for p in points})
    for size in sizes:
        totals = [p.total_ms for p in points if p.n_policies == size]
        reasons = [p.reason_ms for p in points if p.n_policies == size]
        verifies = [p.verify_ms for p in points if p.n_policies == size]
        out[size] = {
            "n": len(totals),
            "total_mean": statistics.mean(totals),
            "total_min": min(totals),
            "total_max": max(totals),
            "reason_mean": statistics.mean(reasons),
            "verify_mean": statistics.mean(verifies),
            "stdev": statistics.stdev(totals) if len(totals) > 1 else 0.0,
        }
    return out


def hardware_fingerprint() -> dict[str, str]:
    import platform
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "machine": platform.machine(),
        "cpu_count": str(os.cpu_count() or 0),
    }
    return info
