"""Benchmark of cost anomaly detectors on synthetic series with known anomalies.

Real billing data has no ground truth, so spikes are injected into generated series
and every detector is scored on the days it flags. The detectors only look for cost
increases, like the production one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional, Set

import numpy as np

from app.services.anomaly_service import (
    BASELINE_WINDOW,
    CONTAMINATION,
    MIN_BASELINE_POINTS,
    MIN_POINTS,
    detect_series_anomalies,
)

SERIES_DAYS = 90
START = date(2026, 1, 5)  # a Monday: the weekly pattern starts on a weekday

Series = Dict[date, float]
Detector = Callable[[Series], Set[date]]


def _flat(rng: np.random.Generator, n: int) -> np.ndarray:
    return 50 + rng.normal(0, 2, n)


def _noisy(rng: np.random.Generator, n: int) -> np.ndarray:
    return 200 + rng.normal(0, 40, n)


def _weekly(rng: np.random.Generator, n: int) -> np.ndarray:
    weekend = np.array([(START + timedelta(days=i)).weekday() >= 5 for i in range(n)])
    return np.where(weekend, 30.0, 60.0) + rng.normal(0, 2, n)


def _growth(rng: np.random.Generator, n: int) -> np.ndarray:
    return 20 * 1.01 ** np.arange(n) + rng.normal(0, 1, n)


def _tiny(rng: np.random.Generator, n: int) -> np.ndarray:
    return np.abs(0.05 + rng.normal(0, 0.03, n))


SCENARIOS: Dict[str, Callable[[np.random.Generator, int], np.ndarray]] = {
    "flat": _flat,
    "noisy": _noisy,
    "weekly": _weekly,
    "growth": _growth,
    "tiny": _tiny,
}

# Bills of a few cents are never worth an alert, so they only test false alarms.
CLEAN_ONLY = {"tiny"}


@dataclass(frozen=True)
class Injection:
    name: str
    multiplier: float
    width: int


INJECTIONS = [
    Injection("spike x1.6", 1.6, 1),
    Injection("spike x2", 2.0, 1),
    Injection("spike x3", 3.0, 1),
    Injection("4-day plateau x3", 3.0, 4),
]


@dataclass(frozen=True)
class Case:
    scenario: str
    injection: Optional[Injection]
    series: Series
    anomaly_days: frozenset


def build_cases(per_group: int, seed: int = 0) -> List[Case]:
    """Clean series for every scenario plus one injected series per scenario and injection."""
    cases: List[Case] = []
    for s, (scenario, generate) in enumerate(SCENARIOS.items()):
        groups: List[Optional[Injection]] = [None]
        if scenario not in CLEAN_ONLY:
            groups += INJECTIONS
        for g, injection in enumerate(groups):
            for i in range(per_group):
                rng = np.random.default_rng([seed, s, g, i])
                values = generate(rng, SERIES_DAYS)
                days: frozenset = frozenset()
                if injection:
                    first = int(rng.integers(MIN_POINTS, SERIES_DAYS - injection.width))
                    values[first:first + injection.width] *= injection.multiplier
                    days = frozenset(START + timedelta(days=first + k) for k in range(injection.width))
                series = {START + timedelta(days=d): float(v) for d, v in enumerate(values)}
                cases.append(Case(scenario, injection, series, days))
    return cases


def _arrays(series: Series) -> tuple[List[date], np.ndarray]:
    days = sorted(series)
    return days, np.array([series[d] for d in days], dtype=float)


def _scan(series: Series, score: Callable[[np.ndarray, float], float], threshold: float) -> Set[date]:
    """Flag the days whose score against the preceding days is above the threshold."""
    days, values = _arrays(series)
    return {
        days[i]
        for i in range(MIN_BASELINE_POINTS, len(values))
        if score(values[max(0, i - BASELINE_WINDOW):i], values[i]) > threshold
    }


def zscore_detector(series: Series) -> Set[date]:
    """Mean and standard deviation of the previous days; flags above 3 standard deviations."""
    def score(window: np.ndarray, value: float) -> float:
        return (value - window.mean()) / max(window.std(), 1e-9)
    return _scan(series, score, 3.0)


def mad_detector(series: Series) -> Set[date]:
    """Median and median absolute deviation of the previous days; flags above 4 robust deviations."""
    def score(window: np.ndarray, value: float) -> float:
        median = np.median(window)
        mad = max(1.4826 * np.median(np.abs(window - median)), 1e-9)
        return (value - median) / mad
    return _scan(series, score, 4.0)


def isolation_forest_detector(series: Series) -> Set[date]:
    """Isolation Forest on the raw daily costs, with no baseline and no guardrails."""
    from sklearn.ensemble import IsolationForest

    days, values = _arrays(series)
    forest = IsolationForest(n_estimators=200, contamination=CONTAMINATION, random_state=42)
    labels = forest.fit_predict(values.reshape(-1, 1))
    median = np.median(values)
    return {d for d, label, v in zip(days, labels, values) if label == -1 and v > median}


def production_detector(series: Series) -> Set[date]:
    return {a.day for a in detect_series_anomalies("benchmark", series)}


DETECTORS: Dict[str, Detector] = {
    "z-score": zscore_detector,
    "median + MAD": mad_detector,
    "Isolation Forest": isolation_forest_detector,
    "production (hybrid)": production_detector,
}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def evaluate(cases: List[Case], detectors: Dict[str, Detector] = None) -> dict:
    """Score every detector: overall counts, recall per injection and false alarms per scenario.

    False alarms are flagged days that are not injected, counted per series.
    """
    result: dict = {}
    for name, detect in (detectors or DETECTORS).items():
        overall = Counts()
        recall_by_injection: Dict[str, Counts] = {}
        false_alarms: Dict[str, List[int]] = {}
        for case in cases:
            flagged = detect(case.series)
            tp = len(flagged & case.anomaly_days)
            fp = len(flagged - case.anomaly_days)
            fn = len(case.anomaly_days - flagged)
            overall.tp, overall.fp, overall.fn = overall.tp + tp, overall.fp + fp, overall.fn + fn
            if case.injection:
                counts = recall_by_injection.setdefault(case.injection.name, Counts())
                counts.tp, counts.fn = counts.tp + tp, counts.fn + fn
            false_alarms.setdefault(case.scenario, []).append(fp)
        result[name] = {
            "overall": overall,
            "recall_by_injection": recall_by_injection,
            "false_alarms_per_series": {k: sum(v) / len(v) for k, v in false_alarms.items()},
        }
    return result


def format_report(result: dict, series_count: int) -> str:
    names = list(result)
    lines = [f"Series per group: {series_count}, {SERIES_DAYS} days each", ""]
    lines += ["| Detector | Precision | Recall | F1 |", "|---|---|---|---|"]
    for name in names:
        c = result[name]["overall"]
        lines.append(f"| {name} | {c.precision:.2f} | {c.recall:.2f} | {c.f1:.2f} |")

    lines += ["", "Recall by injected anomaly", "", "| Detector | " + " | ".join(i.name for i in INJECTIONS) + " |",
              "|---|" + "---|" * len(INJECTIONS)]
    for name in names:
        cells = [f"{result[name]['recall_by_injection'][i.name].recall:.2f}" for i in INJECTIONS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["", "False alarms per series (all flagged days outside the injected ones)", "",
              "| Detector | " + " | ".join(SCENARIOS) + " |", "|---|" + "---|" * len(SCENARIOS)]
    for name in names:
        rates = result[name]["false_alarms_per_series"]
        lines.append(f"| {name} | " + " | ".join(f"{rates[s]:.2f}" for s in SCENARIOS) + " |")
    return "\n".join(lines)
