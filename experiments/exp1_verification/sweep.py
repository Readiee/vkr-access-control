"""Конфигурация полной выборки EXP1: около 80 сценариев по 8 классам

Каждый SweepCase детерминированно генерируется через generator.generate_scenario,
прогоняется через VerificationService, результат сопоставляется с expected
(формат тот же, что и в scenarios_ground_truth.json)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from _common.generator import GenerationConfig


@dataclass(frozen=True)
class SweepCase:
    name: str
    config: GenerationConfig
    expected: dict[str, Any]
    include_subsumption: bool = False


def _happy_cases() -> list[SweepCase]:
    cases: list[SweepCase] = []
    for i, (n_mod, n_act, n_pol) in enumerate(
        [(2, 2, 1), (2, 3, 2), (3, 2, 2), (3, 3, 3), (3, 4, 4), (4, 2, 3),
         (4, 3, 4), (4, 4, 6), (5, 2, 4), (5, 3, 6), (5, 4, 8), (6, 2, 5),
         (6, 3, 6), (2, 4, 2), (3, 5, 5)],
    ):
        cases.append(SweepCase(
            name=f"happy_{i:02d}_m{n_mod}a{n_act}p{n_pol}",
            config=GenerationConfig(
                n_modules=n_mod,
                n_activities_per_module=n_act,
                n_students=2,
                n_policies=n_pol,
                course_id=f"course_happy_{i:02d}",
            ),
            expected={"consistency": "passed", "acyclicity": "passed", "reachability": "passed"},
        ))
    return cases


def _sv1_cases() -> list[SweepCase]:
    cases: list[SweepCase] = []
    sizes = [(2, 2), (2, 3), (3, 2), (3, 3), (3, 4), (4, 2), (4, 3), (5, 2), (2, 4), (5, 4)]
    for i, (n_mod, n_act) in enumerate(sizes):
        cases.append(SweepCase(
            name=f"sv1_{i:02d}",
            config=GenerationConfig(
                n_modules=n_mod,
                n_activities_per_module=n_act,
                n_students=2,
                n_policies=0,
                fault="sv1_disjointness",
                fault_params={"user_id": f"gen_mixed_{i:02d}"},
                course_id=f"course_sv1_{i:02d}",
            ),
            expected={"consistency": "failed"},
        ))
    return cases


def _sv2_cases() -> list[SweepCase]:
    cases: list[SweepCase] = []
    configs = [
        (2, 2, 2), (2, 3, 2), (2, 4, 3), (3, 2, 2), (3, 3, 3),
        (3, 4, 4), (4, 2, 2), (4, 3, 3), (4, 4, 4), (5, 3, 5),
    ]
    for i, (n_mod, n_act, cycle_len) in enumerate(configs):
        element_ids = [f"gen_activity_0_{j}" for j in range(min(cycle_len, n_act))]
        if len(element_ids) < 2:
            continue
        cases.append(SweepCase(
            name=f"sv2_{i:02d}_len{len(element_ids)}",
            config=GenerationConfig(
                n_modules=n_mod,
                n_activities_per_module=n_act,
                n_students=2,
                n_policies=0,
                fault="sv2_cycle",
                fault_params={"element_ids": element_ids},
                course_id=f"course_sv2_{i:02d}",
            ),
            expected={"acyclicity": "failed"},
        ))
    return cases


def _sv3_atomic_cases() -> list[SweepCase]:
    thresholds = [101.0, 110.0, 125.0, 150.0, 175.0, 200.0, -0.5, -10.0, -50.0, 999.0]
    cases: list[SweepCase] = []
    for i, bad in enumerate(thresholds):
        cases.append(SweepCase(
            name=f"sv3_thr_{i:02d}_t{int(bad)}",
            config=GenerationConfig(
                n_modules=2,
                n_activities_per_module=3,
                n_students=2,
                n_policies=0,
                fault="sv3_atomic_threshold",
                fault_params={"element_id": "gen_activity_0_0", "bad_threshold": bad},
                course_id=f"course_sv3_thr_{i:02d}",
            ),
            expected={"reachability": "failed"},
        ))
    return cases


def _sv3_date_cases() -> list[SweepCase]:
    ranges = [
        (dt.datetime(2026, 6, 1), dt.datetime(2026, 5, 1)),
        (dt.datetime(2026, 12, 31), dt.datetime(2026, 1, 1)),
        (dt.datetime(2027, 1, 1), dt.datetime(2026, 1, 1)),
        (dt.datetime(2026, 7, 15), dt.datetime(2026, 7, 14)),
        (dt.datetime(2026, 5, 2), dt.datetime(2026, 5, 1)),
        (dt.datetime(2030, 1, 1), dt.datetime(2026, 1, 1)),
        (dt.datetime(2026, 10, 1), dt.datetime(2026, 9, 30)),
        (dt.datetime(2026, 8, 16), dt.datetime(2026, 8, 15)),
    ]
    cases: list[SweepCase] = []
    for i, (vf, vu) in enumerate(ranges):
        cases.append(SweepCase(
            name=f"sv3_date_{i:02d}",
            config=GenerationConfig(
                n_modules=2,
                n_activities_per_module=3,
                n_students=2,
                n_policies=0,
                fault="sv3_empty_date",
                fault_params={"element_id": "gen_activity_0_0", "valid_from": vf, "valid_until": vu},
                course_id=f"course_sv3_date_{i:02d}",
            ),
            expected={"reachability": "failed"},
        ))
    return cases


def _sv3_structural_cases() -> list[SweepCase]:
    configs = [
        (3, 3), (3, 4), (3, 5), (4, 4), (4, 5), (5, 5), (5, 6), (6, 6), (3, 6), (4, 6),
    ]
    cases: list[SweepCase] = []
    for i, (chain_len, n_act) in enumerate(configs):
        ids = [f"gen_activity_0_{j}" for j in range(chain_len)]
        cases.append(SweepCase(
            name=f"sv3_struct_{i:02d}_len{chain_len}",
            config=GenerationConfig(
                n_modules=1,
                n_activities_per_module=n_act,
                n_students=1,
                n_policies=0,
                fault="sv3_structural",
                fault_params={"element_ids": ids},
                course_id=f"course_sv3_struct_{i:02d}",
            ),
            expected={"reachability": "failed"},
        ))
    return cases


def _sv4_cases() -> list[SweepCase]:
    thresholds = [
        (80.0, 60.0), (90.0, 70.0), (85.0, 50.0), (95.0, 75.0), (70.0, 40.0),
        (100.0, 80.0), (75.0, 25.0), (60.0, 30.0), (85.0, 65.0), (95.0, 55.0),
    ]
    cases: list[SweepCase] = []
    for i, (strong, weak) in enumerate(thresholds):
        cases.append(SweepCase(
            name=f"sv4_{i:02d}_s{int(strong)}w{int(weak)}",
            config=GenerationConfig(
                n_modules=2,
                n_activities_per_module=3,
                n_students=2,
                n_policies=0,
                fault="sv4_redundant",
                fault_params={
                    "element_id": "gen_activity_0_0",
                    "thresholds": (strong, weak),
                },
                course_id=f"course_sv4_{i:02d}",
            ),
            expected={"redundancy": "failed"},
            include_subsumption=True,
        ))
    return cases


def _sv5_cases() -> list[SweepCase]:
    thresholds = [70.0, 75.0, 60.0, 80.0, 50.0, 85.0, 65.0, 90.0, 55.0, 40.0]
    cases: list[SweepCase] = []
    for i, base in enumerate(thresholds):
        cases.append(SweepCase(
            name=f"sv5_{i:02d}_t{int(base)}",
            config=GenerationConfig(
                n_modules=2,
                n_activities_per_module=3,
                n_students=2,
                n_policies=0,
                fault="sv5_subject",
                fault_params={
                    "element_id": "gen_activity_0_0",
                    "group_id": f"gen_grp_adv_{i:02d}",
                    "base_threshold": base,
                },
                course_id=f"course_sv5_{i:02d}",
            ),
            expected={"subsumption": "failed"},
            include_subsumption=True,
        ))
    return cases


def build_cases() -> list[SweepCase]:
    return (
        _happy_cases()
        + _sv1_cases()
        + _sv2_cases()
        + _sv3_atomic_cases()
        + _sv3_date_cases()
        + _sv3_structural_cases()
        + _sv4_cases()
        + _sv5_cases()
    )
