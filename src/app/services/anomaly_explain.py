"""Break a cost spike down into the usage types that caused it.

An anomaly says that a service cost more than expected on a day. This module answers where the
extra money went: for every usage type (and region) of that service it compares the day with the
median of the previous days and keeps the types that explain most of the increase.

It says what grew, not why. The reason (a deployment, a data transfer, a forgotten resource)
is for the person who knows the system.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.services.anomaly_service import BASELINE_WINDOW

# Usage types are kept until together they explain this share of the increase...
COVERED_SHARE = 0.8

# ...but never more than this many are reported.
MAX_DRIVERS = 3

# Increases smaller than this (in dollars) are noise, not a driver.
MIN_DELTA = 0.01

# (substring of the lower-case usage type, description). The first match wins, so the more
# specific patterns come first. Unknown usage types are shown as they are.
CATEGORIES: List[Tuple[str, str]] = [
    ("natgateway-bytes", "data processed by a NAT Gateway"),
    ("natgateway-hours", "NAT Gateway hours"),
    ("loadbalancerusage", "load balancer hours"),
    ("lcuusage", "load balancer capacity units"),
    ("boxusage", "instance hours"),
    ("spotusage", "spot instance hours"),
    ("instanceusage", "database instance hours"),
    ("datatransfer", "data transfer"),
    ("-bytes", "data transfer"),
    ("snapshot", "volume snapshots"),
    ("ebs:", "EBS volumes"),
    ("storage", "storage"),
    ("publicipv4", "public IPv4 addresses"),
    ("elasticip", "Elastic IP addresses"),
    ("gb-second", "function compute time"),
    ("request", "requests"),
]

Key = Tuple[str, str]  # (usage type, region)
Series = Dict[Key, Dict[date, float]]


@dataclass(frozen=True)
class Driver:
    usage_type: str
    region: str
    meaning: Optional[str]
    actual_cost: float
    expected_cost: float
    share: float
    is_new: bool

    @property
    def increase(self) -> float:
        return self.actual_cost - self.expected_cost


def parse_usage_costs(results_by_time: List[dict], metric: str = "UnblendedCost") -> Series:
    """Cost Explorer daily results grouped by (USAGE_TYPE, REGION) into one series per group."""
    series: Series = {}
    for period in results_by_time:
        start = period.get("TimePeriod", {}).get("Start")
        if not start:
            continue
        day = datetime.strptime(start[:10], "%Y-%m-%d").date()
        for group in period.get("Groups", []):
            keys = group.get("Keys") or []
            if len(keys) < 2:
                continue
            try:
                amount = float(group["Metrics"][metric]["Amount"])
            except (KeyError, TypeError, ValueError):
                continue
            days = series.setdefault((keys[0], keys[1]), {})
            days[day] = days.get(day, 0.0) + amount
    return series


def meaning_of(usage_type: str) -> Optional[str]:
    lowered = usage_type.lower()
    return next((text for pattern, text in CATEGORIES if pattern in lowered), None)


def explain_spike(series: Series, day: date) -> List[Driver]:
    """The usage types behind the increase of one day, largest first. Empty if nothing increased."""
    window = [day - timedelta(days=i) for i in range(BASELINE_WINDOW, 0, -1)]
    increases = []
    for (usage_type, region), costs in series.items():
        history = [costs.get(d, 0.0) for d in window]
        expected = float(np.median(history))
        actual = costs.get(day, 0.0)
        if actual - expected >= MIN_DELTA:
            increases.append((usage_type, region, actual, expected, not any(history)))

    total = sum(actual - expected for _, _, actual, expected, _ in increases)
    drivers: List[Driver] = []
    covered = 0.0
    for usage_type, region, actual, expected, is_new in sorted(increases, key=lambda i: i[2] - i[3], reverse=True):
        if len(drivers) == MAX_DRIVERS or covered >= COVERED_SHARE:
            break
        share = (actual - expected) / total
        covered += share
        drivers.append(Driver(usage_type, region, meaning_of(usage_type), round(actual, 2), round(expected, 2), share, is_new))
    return drivers


def describe_drivers(drivers: List[Driver]) -> Optional[str]:
    """One line for a notification, or None when there is nothing to say."""
    if not drivers:
        return None
    parts = []
    for d in drivers:
        text = f"`{d.usage_type}` ({d.region}"
        text += f", {d.meaning})" if d.meaning else ")"
        text += f" +${d.increase:.2f} ({d.share:.0%} of the increase)"
        parts.append(text + (", new" if d.is_new else ""))
    return "main driver: " + "; ".join(parts)
