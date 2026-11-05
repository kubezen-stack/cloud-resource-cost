from datetime import date

from app.services.anomaly_alerts import anomalies_on, describe
from app.services.anomaly_service import Anomaly


def anomaly(day, pct=140.0, service="Amazon EC2"):
    return Anomaly(service=service, day=day, actual_cost=120.0, expected_cost=50.0, deviation_pct=pct, anomaly_score=0.7)


def test_only_the_requested_day_is_reported():
    found = [anomaly(date(2026, 11, 2)), anomaly(date(2026, 11, 3)), anomaly(date(2026, 11, 2), service="S3")]
    assert [a.service for a in anomalies_on(found, date(2026, 11, 2))] == ["Amazon EC2", "S3"]
    assert anomalies_on(found, date(2026, 11, 4)) == []


def test_description_shows_actual_expected_and_increase():
    assert describe(anomaly(date(2026, 11, 2))) == "Amazon EC2: `$120.0` instead of `$50.0` (+140%)"


def test_description_without_percentage_when_baseline_is_zero():
    assert describe(anomaly(date(2026, 11, 2), pct=None)) == "Amazon EC2: `$120.0` instead of `$50.0`"
