from datetime import date, timedelta
from unittest.mock import patch
import numpy as np
import pytest
from app.services import anomaly_service
from app.services.anomaly_service import (
    detect_anomalies,
    detect_series_anomalies,
    parse_daily_service_costs,
)

START = date(2026, 7, 1)


def series_from(values, start=START):
    return {start + timedelta(days=i): float(v) for i, v in enumerate(values)}

def results_by_time(per_service, start=START):
    length = max(len(v) for v in per_service.values())
    results = []
    for i in range(length):
        day = start + timedelta(days=i)
        groups = [
            {"Keys": [name], "Metrics": {"UnblendedCost": {"Amount": str(values[i]), "Unit": "USD"}}}
            for name, values in per_service.items()
            if i < len(values)
        ]
        results.append({
            "TimePeriod": {"Start": day.isoformat(), "End": (day + timedelta(days=1)).isoformat()},
            "Groups": groups,
        })
    return results

class TestParse:
    def test_groups_by_service_and_day(self):
        data = results_by_time({"EC2": [1, 2], "S3": [3, 4]})
        parsed = parse_daily_service_costs(data)
        assert parsed["EC2"] == {START: 1.0, START + timedelta(days=1): 2.0}
        assert parsed["S3"][START] == 3.0

    def test_sums_duplicate_rows_for_same_day(self):
        data = results_by_time({"EC2": [1]})
        data[0]["Groups"].append(
            {"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "4", "Unit": "USD"}}}
        )
        assert parse_daily_service_costs(data)["EC2"][START] == 5.0

    def test_skips_malformed_rows(self):
        data = [
            {"TimePeriod": {}, "Groups": []},
            {"TimePeriod": {"Start": "2026-07-01"}, "Groups": [
                {"Keys": [], "Metrics": {}},
                {"Keys": ["EC2"], "Metrics": {}},
                {"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "oops"}}},
                {"Keys": ["S3"], "Metrics": {"UnblendedCost": {"Amount": "2.5"}}},
            ]},
        ]
        assert parse_daily_service_costs(data) == {"S3": {START: 2.5}}

class TestDetectSeries:
    def test_flags_a_clear_spike(self):
        rng = np.random.default_rng(0)
        values = 50 + rng.normal(0, 2, 60)
        values[45] = 150

        found = detect_series_anomalies("Amazon EC2", series_from(values))

        assert [a.day for a in found] == [START + timedelta(days=45)]
        anomaly = found[0]
        assert anomaly.service == "Amazon EC2"
        assert anomaly.actual_cost == 150.0
        assert anomaly.expected_cost == pytest.approx(50, abs=3)
        assert anomaly.deviation_pct == pytest.approx(200, abs=15)
        assert 0 < anomaly.anomaly_score <= 1

    def test_flags_a_spike_on_the_most_recent_day(self):
        rng = np.random.default_rng(1)
        values = 50 + rng.normal(0, 2, 40)
        values[-1] = 130

        found = detect_series_anomalies("EC2", series_from(values))

        assert [a.day for a in found] == [START + timedelta(days=39)]

    @pytest.mark.parametrize("seed", range(25))
    def test_flat_noisy_series_has_no_anomalies(self, seed):
        rng = np.random.default_rng(seed)
        values = 50 + rng.normal(0, 2, 90)
        assert detect_series_anomalies("EC2", series_from(values)) == []

    @pytest.mark.parametrize("seed", range(10))
    def test_weekly_seasonality_is_not_an_anomaly(self, seed):
        rng = np.random.default_rng(seed)
        values = np.array(
            [30 if (START + timedelta(days=i)).weekday() >= 5 else 60 for i in range(90)]
        ) + rng.normal(0, 2, 90)
        assert detect_series_anomalies("EC2", series_from(values)) == []

    @pytest.mark.parametrize("seed", range(10))
    def test_steady_growth_is_not_an_anomaly(self, seed):
        rng = np.random.default_rng(seed)
        values = 20 * 1.01 ** np.arange(90) + rng.normal(0, 1, 90)
        assert detect_series_anomalies("EC2", series_from(values)) == []

    def test_cost_drop_is_not_reported(self):
        rng = np.random.default_rng(2)
        values = 50 + rng.normal(0, 2, 60)
        values[40] = 0
        assert detect_series_anomalies("EC2", series_from(values)) == []

    def test_spike_in_pennies_is_ignored(self):
        rng = np.random.default_rng(3)
        values = np.abs(0.05 + rng.normal(0, 0.01, 60))
        values[40] = 0.5
        assert detect_series_anomalies("KMS", series_from(values)) == []

    def test_modest_bump_below_threshold_is_ignored(self):
        rng = np.random.default_rng(4)
        values = 50 + rng.normal(0, 2, 60)
        values[40] = 70
        assert detect_series_anomalies("EC2", series_from(values)) == []

    def test_new_service_with_no_history_has_no_percentage(self):
        values = np.zeros(40)
        values[-1] = 25
        found = detect_series_anomalies("NAT Gateway", series_from(values))

        assert len(found) == 1
        assert found[0].expected_cost == 0
        assert found[0].deviation_pct is None

    def test_too_little_history_returns_nothing(self):
        values = [10] * (anomaly_service.MIN_POINTS - 1)
        assert detect_series_anomalies("EC2", series_from(values)) == []

    def test_all_zero_series_returns_nothing(self):
        assert detect_series_anomalies("EC2", series_from([0] * 60)) == []

    def test_missing_days_are_treated_as_zero_cost(self):
        rng = np.random.default_rng(5)
        values = 50 + rng.normal(0, 2, 60)
        series = series_from(values)
        for i in (10, 11, 12):
            del series[START + timedelta(days=i)]
        series[START + timedelta(days=45)] = 150.0

        found = detect_series_anomalies("EC2", series)

        assert START + timedelta(days=45) in [a.day for a in found]

    def test_is_deterministic(self):
        rng = np.random.default_rng(6)
        values = 50 + rng.normal(0, 2, 60)
        values[30] = 140
        first = detect_series_anomalies("EC2", series_from(values))
        second = detect_series_anomalies("EC2", series_from(values))
        assert first == second

class TestDetectAll:
    def test_only_the_anomalous_service_is_reported(self):
        rng = np.random.default_rng(7)
        ec2 = list(50 + rng.normal(0, 2, 60))
        s3 = list(10 + rng.normal(0, 0.3, 60))
        ec2[50] = 160

        found = detect_anomalies(results_by_time({"Amazon EC2": ec2, "Amazon S3": s3}))

        assert [(a.service, a.day) for a in found] == [("Amazon EC2", START + timedelta(days=50))]

    def test_results_are_sorted_newest_first(self):
        rng = np.random.default_rng(8)
        ec2 = list(50 + rng.normal(0, 2, 60))
        rds = list(80 + rng.normal(0, 2, 60))
        ec2[30] = 160
        rds[50] = 240

        found = detect_anomalies(results_by_time({"EC2": ec2, "RDS": rds}))

        assert [a.service for a in found] == ["RDS", "EC2"]

    def test_one_failing_service_does_not_hide_the_others(self):
        rng = np.random.default_rng(9)
        ec2 = list(50 + rng.normal(0, 2, 60))
        rds = list(80 + rng.normal(0, 2, 60))
        ec2[40] = 160
        rds[40] = 240
        real = anomaly_service.detect_series_anomalies

        def flaky(service, series):
            if service == "EC2":
                raise RuntimeError("boom")
            return real(service, series)

        with patch.object(anomaly_service, "detect_series_anomalies", side_effect=flaky):
            found = detect_anomalies(results_by_time({"EC2": ec2, "RDS": rds}))

        assert [a.service for a in found] == ["RDS"]

    def test_empty_input(self):
        assert detect_anomalies([]) == []