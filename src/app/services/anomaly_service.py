from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from sklearn.ensemble import IsolationForest
import numpy as np

logger = logging.getLogger(__name__)

# Days of history needed before a series is analysed at all.
MIN_POINTS = 21

# Window (in days) of the rolling median used as the "expected" cost.
BASELINE_WINDOW = 14

# Minimum number of preceding days required to compute a baseline for a day.
MIN_BASELINE_POINTS = 7

# Expected share of outliers the forest assumes. Guardrails below do the
# real filtering, this only controls how many days compete for the label.
CONTAMINATION = 0.05

# A spike must be at least this much above the baseline (0.5 = +50%)...
MIN_RELATIVE_DEVIATION = 0.5

# and at least this many dollars above it (ignores noise on tiny bills).
MIN_ABSOLUTE_DEVIATION = 1.0

# and at least this many robust standard deviations above it, so a bill
# that is naturally jumpy needs a bigger jump to count as an anomaly.
MIN_SIGMA_MULTIPLE = 4.0

# Floor used when scaling, so a ~$0 baseline does not explode the features.
SCALE_FLOOR = 1.0

# Converts a median absolute residual into a standard-deviation estimate.
MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class Anomaly:
    service: str
    day: date
    actual_cost: float
    expected_cost: float
    deviation_pct: Optional[float]
    anomaly_score: float


def parse_daily_service_costs(
    results_by_time: List[dict], metric: str = "UnblendedCost"
) -> Dict[str, Dict[date, float]]:
    series: Dict[str, Dict[date, float]] = {}
    for period in results_by_time:
        start = period.get("TimePeriod", {}).get("Start")
        if not start:
            continue
        day = datetime.strptime(start[:10], "%Y-%m-%d").date()
        for group in period.get("Groups", []):
            keys = group.get("Keys") or []
            if not keys:
                continue
            try:
                amount = float(group["Metrics"][metric]["Amount"])
            except (KeyError, TypeError, ValueError):
                continue
            service_days = series.setdefault(keys[0], {})
            service_days[day] = service_days.get(day, 0.0) + amount
    return series


def _dense(series: Dict[date, float]) -> tuple[List[date], np.ndarray]:
    first, last = min(series), max(series)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    return days, np.array([series.get(d, 0.0) for d in days], dtype=float)


def _baseline(values: np.ndarray) -> np.ndarray:
    baseline = np.full(len(values), np.nan)
    for i in range(MIN_BASELINE_POINTS, len(values)):
        window = values[max(0, i - BASELINE_WINDOW):i]
        baseline[i] = np.median(window)
    return baseline


def detect_series_anomalies(service: str, series: Dict[date, float]) -> List[Anomaly]:
    if len(series) < MIN_POINTS:
        return []

    days, values = _dense(series)
    if len(values) < MIN_POINTS or not np.any(values > 0):
        return []

    baseline = _baseline(values)
    candidates = np.where(~np.isnan(baseline))[0]
    if len(candidates) < MIN_POINTS - MIN_BASELINE_POINTS:
        return []

    expected = baseline[candidates]
    actual = values[candidates]
    residual = actual - expected

    noise = max(float(np.median(np.abs(residual))), 0.01 * max(float(np.median(actual)), SCALE_FLOOR))

    features = np.column_stack([
        residual / np.maximum(expected, SCALE_FLOOR),
        residual / noise,
    ])

    forest = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=42,
    )
    labels = forest.fit_predict(features)
    scores = -forest.score_samples(features)

    min_jump = MIN_SIGMA_MULTIPLE * MAD_TO_SIGMA * noise

    found: List[Anomaly] = []
    for idx, label in enumerate(labels):
        if label != -1:
            continue
        exp, act = float(expected[idx]), float(actual[idx])
        diff = act - exp
        if diff < MIN_ABSOLUTE_DEVIATION or diff < min_jump:
            continue
        if exp > 0 and diff / exp < MIN_RELATIVE_DEVIATION:
            continue
        found.append(
            Anomaly(
                service=service,
                day=days[candidates[idx]],
                actual_cost=round(act, 2),
                expected_cost=round(exp, 2),
                deviation_pct=round(diff / exp * 100, 2) if exp > 0 else None,
                anomaly_score=round(float(scores[idx]), 4),
            )
        )
    return found


def detect_anomalies(
    results_by_time: List[dict], metric: str = "UnblendedCost"
) -> List[Anomaly]:
    anomalies: List[Anomaly] = []
    for service, series in parse_daily_service_costs(results_by_time, metric).items():
        try:
            anomalies.extend(detect_series_anomalies(service, series))
        except Exception:
            logger.exception("Anomaly detection failed for service %s", service)
    anomalies.sort(key=lambda a: (a.day, a.anomaly_score), reverse=True)
    return anomalies