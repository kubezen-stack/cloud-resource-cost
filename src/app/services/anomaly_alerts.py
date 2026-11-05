"""Choose the anomalies that deserve a notification and describe them in one line each."""
from datetime import date
from typing import Iterable, List

from app.services.anomaly_service import Anomaly


def anomalies_on(anomalies: Iterable[Anomaly], day: date) -> List[Anomaly]:
    """Anomalies of one day. A daily job reports each flagged day once, when it is two days old."""
    return [a for a in anomalies if a.day == day]


def describe(anomaly: Anomaly) -> str:
    text = f"{anomaly.service}: `${anomaly.actual_cost}` instead of `${anomaly.expected_cost}`"
    if anomaly.deviation_pct is not None:
        text += f" (+{anomaly.deviation_pct:.0f}%)"
    return text
