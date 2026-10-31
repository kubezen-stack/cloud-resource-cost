import numpy as np
import pytest

from app.services.rightsizing_service import (
    MIN_HOURS,
    InstanceMetrics,
    parse_instance_type,
    recommend,
)

HOURS = 24 * 14


def metrics(instance_type="m5.xlarge", avg=10.0, peak=25.0, hours=HOURS, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    hourly_avg = list(np.clip(avg + rng.normal(0, noise, hours), 0, 100))
    hourly_max = [min(100.0, max(v, peak)) for v in hourly_avg]
    return InstanceMetrics("i-123", "web", instance_type, "us-east-1", hourly_avg, hourly_max)


def test_parse_instance_type():
    assert parse_instance_type("m5.xlarge") == ("m5", "xlarge")
    assert parse_instance_type("t3.2xlarge") == ("t3", "2xlarge")
    assert parse_instance_type("c5.metal") is None
    assert parse_instance_type("garbage") is None


def test_insufficient_history_gives_no_advice():
    rec = recommend(metrics(hours=MIN_HOURS - 1))
    assert rec.action == "insufficient_data"
    assert rec.recommended_type is None
    assert rec.hours_observed == MIN_HOURS - 1


def test_underused_instance_is_downsized_one_step():
    rec = recommend(metrics("m5.xlarge", avg=10, peak=25, noise=1))
    assert rec.action == "downsize"
    assert rec.recommended_type == "m5.large"
    assert rec.estimated_savings_pct == 50.0
    assert rec.cpu_max == 25.0


def test_downsize_is_refused_when_peak_would_not_fit():
    # avg is low, but the peak would hit 2 x 60 = 120% on the smaller size.
    rec = recommend(metrics("m5.xlarge", avg=10, peak=60, noise=1))
    assert rec.action == "keep"
    assert rec.recommended_type is None


def test_busy_instance_is_kept():
    rec = recommend(metrics("m5.xlarge", avg=45, peak=70, noise=3))
    assert rec.action == "keep"


def test_overloaded_instance_gets_upsize_warning():
    rec = recommend(metrics("m5.large", avg=88, peak=99, noise=2))
    assert rec.action == "upsize"
    assert rec.estimated_savings_pct is None


def test_idle_instance_is_flagged():
    rec = recommend(metrics("m5.2xlarge", avg=1.5, peak=4, noise=0.3))
    assert rec.action == "idle"
    assert rec.estimated_savings_pct == 100.0


def test_smallest_non_burstable_size_is_kept():
    rec = recommend(metrics("m5.large", avg=10, peak=20, noise=1))
    assert rec.action == "keep"
    assert "smallest" in rec.reason


def test_burstable_family_can_go_down_to_nano():
    rec = recommend(metrics("t3.micro", avg=5, peak=12, noise=0.5))
    assert rec.action == "downsize"
    assert rec.recommended_type == "t3.nano"


def test_smallest_burstable_size_is_kept():
    rec = recommend(metrics("t3.nano", avg=10, peak=20, noise=1))
    assert rec.action == "keep"


def test_unknown_type_needs_manual_review():
    rec = recommend(metrics("c5.metal", avg=20, peak=40, noise=1))
    assert rec.action == "unsupported"


def test_statistics_are_reported():
    rec = recommend(metrics("m5.xlarge", avg=20, peak=40, noise=0))
    assert rec.cpu_avg == 20.0
    assert rec.cpu_p95 == 20.0
    assert rec.cpu_max == 40.0
