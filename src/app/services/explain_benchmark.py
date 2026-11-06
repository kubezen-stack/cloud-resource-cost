"""Benchmark of spike attribution on synthetic services with a known cause.

A service is built from several usage types with their own level and noise. One spike is injected
into a known usage type and every method has to name it. This measures the attribution, not the
detection of the spike (see anomaly_benchmark for that).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

import numpy as np

from app.services.anomaly_explain import Series, explain_spike
from app.services.anomaly_service import BASELINE_WINDOW

DAY = date(2026, 11, 3)
REGION = "eu-central-1"

# usage type: (daily cost, relative noise). Some lines are large and steady, some small and jumpy.
LAYOUT: Dict[str, tuple] = {
    "EUC1-BoxUsage:m6i.large": (120.0, 0.05),
    "EUC1-NatGateway-Hours": (3.0, 0.02),
    "EUC1-NatGateway-Bytes": (4.0, 0.30),
    "EUC1-DataTransfer-Out-Bytes": (8.0, 0.25),
    "EBS:VolumeUsage.gp3": (15.0, 0.03),
    "EUC1-Requests-Tier1": (1.5, 0.20),
}
NEW_TYPE = "EUC1-DataTransfer-Regional-Bytes"

Method = Callable[[Series], Optional[str]]


@dataclass(frozen=True)
class Trial:
    series: Series
    cause: str


def _base_series(rng: np.random.Generator) -> Series:
    series: Series = {}
    for usage_type, (level, noise) in LAYOUT.items():
        days = [DAY - timedelta(days=i) for i in range(BASELINE_WINDOW, -1, -1)]
        costs = np.clip(rng.normal(level, level * noise, len(days)), 0, None)
        series[(usage_type, REGION)] = {d: float(c) for d, c in zip(days, costs)}
    return series


def _random_types(rng: np.random.Generator, count: int) -> List[str]:
    return [str(t) for t in rng.choice(list(LAYOUT), size=count, replace=False)]


def _spike_x3(series: Series, rng: np.random.Generator) -> str:
    (cause,) = _random_types(rng, 1)
    series[(cause, REGION)][DAY] *= 3
    return cause


def _extra_50(series: Series, rng: np.random.Generator) -> str:
    (cause,) = _random_types(rng, 1)
    series[(cause, REGION)][DAY] += 50.0
    return cause


def _new_type(series: Series, rng: np.random.Generator) -> str:
    series[(NEW_TYPE, REGION)] = {DAY: 50.0}
    return NEW_TYPE


def _two_spikes(series: Series, rng: np.random.Generator) -> str:
    big, small = _random_types(rng, 2)
    series[(big, REGION)][DAY] += 80.0
    series[(small, REGION)][DAY] += 30.0
    return big


SCENARIOS: Dict[str, Callable[[Series, np.random.Generator], str]] = {
    "one type costs 3x": _spike_x3,
    "one type gets +$50": _extra_50,
    "a new usage type (+$50)": _new_type,
    "two types, +$80 and +$30": _two_spikes,
}


def build_trials(scenario: str, count: int, seed: int = 0) -> List[Trial]:
    index = list(SCENARIOS).index(scenario)
    trials = []
    for i in range(count):
        rng = np.random.default_rng([seed, index, i])
        series = _base_series(rng)
        trials.append(Trial(series, SCENARIOS[scenario](series, rng)))
    return trials


def _expected(costs: Dict[date, float]) -> float:
    return float(np.median([costs.get(DAY - timedelta(days=i), 0.0) for i in range(1, BASELINE_WINDOW + 1)]))


def largest_cost(series: Series) -> Optional[str]:
    """Look at the day's bill and take the biggest line."""
    return max(series, key=lambda k: series[k].get(DAY, 0.0))[0]


def largest_ratio(series: Series) -> Optional[str]:
    """The line that grew the most relative to its usual cost."""
    return max(series, key=lambda k: series[k].get(DAY, 0.0) / max(_expected(series[k]), 0.01))[0]


def largest_increase(series: Series) -> Optional[str]:
    """The production method: the line with the biggest increase over its median."""
    drivers = explain_spike(series, DAY)
    return drivers[0].usage_type if drivers else None


METHODS: Dict[str, Method] = {
    "biggest line of the bill": largest_cost,
    "biggest relative growth": largest_ratio,
    "biggest increase over the median (production)": largest_increase,
}


def evaluate(count: int, seed: int = 0, methods: Dict[str, Method] = None) -> Dict[str, Dict[str, float]]:
    """Share of trials in which each method names the injected usage type, per scenario."""
    result: Dict[str, Dict[str, float]] = {}
    for scenario in SCENARIOS:
        trials = build_trials(scenario, count, seed)
        for name, method in (methods or METHODS).items():
            hits = sum(method(t.series) == t.cause for t in trials)
            result.setdefault(name, {})[scenario] = hits / count
    return result


def format_report(result: Dict[str, Dict[str, float]], count: int) -> str:
    lines = [f"Trials per scenario: {count}. Share of trials where the injected usage type is named first.", "",
             "| Method | " + " | ".join(SCENARIOS) + " | Average |", "|---|" + "---|" * (len(SCENARIOS) + 1)]
    for name, scores in result.items():
        cells = [f"{scores[s]:.2f}" for s in SCENARIOS]
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {sum(scores.values()) / len(scores):.2f} |")
    return "\n".join(lines)
