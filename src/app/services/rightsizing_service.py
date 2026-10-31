from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

# Relative size units: price and capacity roughly double with every step.
SIZE_UNITS = {
    "nano": 1, "micro": 2, "small": 4, "medium": 8, "large": 16,
    "xlarge": 32, "2xlarge": 64, "4xlarge": 128, "8xlarge": 256,
    "12xlarge": 384, "16xlarge": 512, "24xlarge": 768, "32xlarge": 1024,
}
SIZE_ORDER = sorted(SIZE_UNITS, key=SIZE_UNITS.get)

# Hours of hourly data required before giving advice (7 days).
MIN_HOURS = 24 * 7
IDLE_P95 = 5.0
IDLE_MAX = 10.0
OVERLOADED_P95 = 80.0

# After a downsize the instance must stay under these CPU levels.
TARGET_P95 = 60.0
TARGET_MAX = 95.0

ACTIONS = ("downsize", "idle", "upsize", "keep", "unsupported", "insufficient_data")


@dataclass(frozen=True)
class InstanceMetrics:
    instance_id: str
    name: Optional[str]
    instance_type: str
    region: str
    hourly_avg: List[float]
    hourly_max: List[float]


@dataclass(frozen=True)
class Recommendation:
    instance_id: str
    name: Optional[str]
    region: str
    instance_type: str
    action: str
    recommended_type: Optional[str]
    estimated_savings_pct: Optional[float]
    cpu_avg: Optional[float]
    cpu_p95: Optional[float]
    cpu_max: Optional[float]
    hours_observed: int
    reason: str


def parse_instance_type(instance_type: str) -> Optional[tuple[str, str]]:
    """'m5.xlarge' -> ('m5', 'xlarge'); None if the type is not understood."""
    family, dot, size = instance_type.partition(".")
    if not dot or not family or size not in SIZE_UNITS:
        return None
    return family, size


def _smallest_size(family: str) -> str:
    """Burstable t-families go down to nano, the others to large."""
    burstable = family.startswith("t") and len(family) > 1 and family[1].isdigit()
    return "nano" if burstable else "large"


def _smaller_type(family: str, size: str) -> Optional[str]:
    index = SIZE_ORDER.index(size)
    if index == 0 or SIZE_UNITS[size] <= SIZE_UNITS[_smallest_size(family)]:
        return None
    return f"{family}.{SIZE_ORDER[index - 1]}"


def recommend(metrics: InstanceMetrics) -> Recommendation:
    hours = min(len(metrics.hourly_avg), len(metrics.hourly_max))

    def result(action, reason, recommended=None, savings=None, stats=None):
        avg, p95, peak = stats if stats else (None, None, None)
        return Recommendation(
            instance_id=metrics.instance_id,
            name=metrics.name,
            region=metrics.region,
            instance_type=metrics.instance_type,
            action=action,
            recommended_type=recommended,
            estimated_savings_pct=savings,
            cpu_avg=avg,
            cpu_p95=p95,
            cpu_max=peak,
            hours_observed=hours,
            reason=reason,
        )

    parsed = parse_instance_type(metrics.instance_type)
    if hours < MIN_HOURS:
        return result("insufficient_data", f"Only {hours}h of CPU history, need at least {MIN_HOURS}h")

    avg_values = np.asarray(metrics.hourly_avg[:hours], dtype=float)
    max_values = np.asarray(metrics.hourly_max[:hours], dtype=float)
    stats = (
        round(float(avg_values.mean()), 2),
        round(float(np.percentile(avg_values, 95)), 2),
        round(float(max_values.max()), 2),
    )
    _, p95, peak = stats

    if p95 < IDLE_P95 and peak < IDLE_MAX:
        return result(
            "idle",
            f"CPU almost unused (p95 {p95}%, max {peak}%): consider stopping or terminating",
            savings=100.0,
            stats=stats,
        )

    if p95 >= OVERLOADED_P95:
        return result(
            "upsize",
            f"CPU is heavily loaded (p95 {p95}%): risk of throttling, consider a larger type",
            stats=stats,
        )

    if parsed is None:
        return result(
            "unsupported",
            f"Instance type {metrics.instance_type} is not covered by the size ladder: review manually",
            stats=stats,
        )

    family, size = parsed
    target = _smaller_type(family, size)
    if target is None:
        return result("keep", f"Already the smallest size of the {family} family", stats=stats)

    ratio = SIZE_UNITS[size] / SIZE_UNITS[target.split(".")[1]]
    projected_p95, projected_max = p95 * ratio, peak * ratio
    if projected_p95 <= TARGET_P95 and projected_max <= TARGET_MAX:
        savings = round((1 - 1 / ratio) * 100, 1)
        return result(
            "downsize",
            f"Projected CPU on {target}: p95 {projected_p95:.0f}%, max {projected_max:.0f}% (within limits)",
            recommended=target,
            savings=savings,
            stats=stats,
        )

    return result(
        "keep",
        f"Smaller size would reach p95 {projected_p95:.0f}%, max {projected_max:.0f}%: size is appropriate",
        stats=stats,
    )


def recommend_all(instances: List[InstanceMetrics]) -> List[Recommendation]:
    return [recommend(m) for m in instances]
