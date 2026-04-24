"""Метрики экспериментов фазы 3.

Confusion matrix per-property, Precision/Recall/F1 с macro-average,
форматтеры в markdown и CSV. Positive class — обнаруженное нарушение
(status=failed). TP: предсказано failed и в ground-truth failed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

PropertyName = str
DEFAULT_PROPERTIES: tuple[PropertyName, ...] = (
    "consistency",
    "acyclicity",
    "reachability",
    "redundancy",
    "subsumption",
)


@dataclass(frozen=True)
class ConfusionMatrix:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def support(self) -> int:
        return self.tp + self.fn

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else math.nan

    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else math.nan

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        if math.isnan(p) or math.isnan(r) or (p + r) == 0:
            return math.nan
        return 2 * p * r / (p + r)


def build_confusion_matrix(points: Iterable[tuple[bool, bool]]) -> ConfusionMatrix:
    tp = fp = fn = tn = 0
    for predicted, actual in points:
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1
    return ConfusionMatrix(tp=tp, fp=fp, fn=fn, tn=tn)


def extract_points(
    scenarios: Sequence[tuple[Mapping, Mapping]],
    property_name: PropertyName,
) -> list[tuple[bool, bool]]:
    """Точки (predicted_violated, actual_violated) по одному свойству.

    Каждый элемент scenarios — пара (report_properties, expected).
    report_properties: dict property → объект со .status или dict со status.
    expected: spec["expected"] из ground_truth.json.
    Сценарии без заявленного property в expected пропускаются.
    """
    points: list[tuple[bool, bool]] = []
    for report_properties, expected in scenarios:
        exp_value = expected.get(property_name)
        if not isinstance(exp_value, str):
            continue
        prop = report_properties.get(property_name)
        if prop is None:
            raise KeyError(
                f"Свойство {property_name!r} заявлено в expected, но отсутствует в отчёте"
            )
        points.append((_status(prop) == "failed", exp_value == "failed"))
    return points


def _status(prop) -> str:
    if hasattr(prop, "status"):
        return prop.status
    if isinstance(prop, Mapping) and "status" in prop:
        return prop["status"]
    raise TypeError(f"Не могу извлечь status из {type(prop).__name__}")


def aggregate_by_property(
    scenarios: Sequence[tuple[Mapping, Mapping]],
    properties: Sequence[PropertyName] = DEFAULT_PROPERTIES,
) -> dict[PropertyName, ConfusionMatrix]:
    return {
        prop: build_confusion_matrix(extract_points(scenarios, prop))
        for prop in properties
    }


def macro_average(
    matrices: Mapping[PropertyName, ConfusionMatrix],
) -> dict[str, float]:
    bucket: dict[str, list[float]] = {"precision": [], "recall": [], "f1": []}
    for m in matrices.values():
        if m.total == 0:
            continue
        for key, value in (
            ("precision", m.precision()),
            ("recall", m.recall()),
            ("f1", m.f1()),
        ):
            if not math.isnan(value):
                bucket[key].append(value)
    return {k: (sum(v) / len(v) if v else math.nan) for k, v in bucket.items()}


def format_markdown_table(
    matrices: Mapping[PropertyName, ConfusionMatrix],
    include_macro: bool = True,
) -> str:
    lines = [
        "| Свойство | TP | FP | FN | TN | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for prop, m in matrices.items():
        lines.append(
            f"| {prop} | {m.tp} | {m.fp} | {m.fn} | {m.tn} | "
            f"{_fmt(m.precision())} | {_fmt(m.recall())} | {_fmt(m.f1())} | {m.support} |"
        )
    if include_macro:
        macro = macro_average(matrices)
        lines.append(
            f"| **macro-avg** | . | . | . | . | "
            f"{_fmt(macro['precision'])} | {_fmt(macro['recall'])} | {_fmt(macro['f1'])} | . |"
        )
    return "\n".join(lines)


def format_csv(matrices: Mapping[PropertyName, ConfusionMatrix]) -> str:
    rows = ["property,tp,fp,fn,tn,precision,recall,f1,support"]
    for prop, m in matrices.items():
        rows.append(
            f"{prop},{m.tp},{m.fp},{m.fn},{m.tn},"
            f"{_fmt(m.precision(), 4)},{_fmt(m.recall(), 4)},{_fmt(m.f1(), 4)},{m.support}"
        )
    return "\n".join(rows) + "\n"


def _fmt(value: float, precision: int = 3) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.{precision}f}"
