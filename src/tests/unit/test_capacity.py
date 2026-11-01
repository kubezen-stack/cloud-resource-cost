import pytest

from app.schemas.advisor import AdvisorPlan, CapacityInputs
from app.services.capacity import add_measurement_question, check_capacity, required_vcpu


def make_plan(count=4, max_count=4, vcpu=2, capacity=True, source="assumption", zones=2, questions=None):
    return AdvisorPlan.model_validate({
        "summary": "s",
        "capacity": {"peak_rps": 200, "cpu_ms_per_request": 20, "cpu_ms_source": source,
                     "target_utilisation": 0.6, "availability_zones": zones} if capacity else None,
        "components": [{"name": "app", "aws_service": "EC2", "sizing": "x", "rationale": "r", "role": "compute",
                        "instance_count": count, "max_instances": max_count, "vcpu_per_instance": vcpu}],
        "open_questions": questions or [],
    })


def codes(plan):
    return {f.code for f in check_capacity(plan)}


def test_required_vcpu_formula():
    assert required_vcpu(CapacityInputs(peak_rps=200, cpu_ms_per_request=20, target_utilisation=0.6)) == pytest.approx(6.6667, abs=1e-3)


def test_enough_capacity_passes():
    assert check_capacity(make_plan(count=2, max_count=4, vcpu=2)) == []  # peak 8 vCPU >= 6.67


def test_shortfall_is_blocking():
    findings = check_capacity(make_plan(count=2, max_count=2, vcpu=2))  # 4 vCPU < 6.67
    assert [f.code for f in findings] == ["shortfall"] and findings[0].blocking


def test_autoscaling_maximum_counts_for_peak():
    assert "shortfall" not in codes(make_plan(count=2, max_count=6, vcpu=2))


def test_fewer_instances_than_zones_is_blocking():
    findings = check_capacity(make_plan(count=1, max_count=8, vcpu=2, zones=2))
    assert any(f.code == "few_instances" and f.blocking for f in findings)


def test_missing_max_is_only_a_warning():
    findings = check_capacity(make_plan(count=4, max_count=None, vcpu=2))
    assert [f.code for f in findings] == ["no_max"] and not findings[0].blocking


def test_max_below_count_is_blocking():
    assert any(f.code == "bad_max" and f.blocking for f in check_capacity(make_plan(count=4, max_count=2, vcpu=4)))


def test_no_capacity_inputs_is_flagged():
    assert codes(make_plan(capacity=False)) == {"unverified"}


def test_compute_without_sizes_cannot_be_verified():
    plan = make_plan()
    plan.components[0].vcpu_per_instance = None
    assert codes(plan) == {"no_compute"}


def test_plan_without_compute_and_capacity_has_no_findings():
    plan = AdvisorPlan.model_validate({"summary": "s", "components": [
        {"name": "site", "aws_service": "S3", "sizing": "x", "rationale": "r"}]})
    assert check_capacity(plan) == []


def test_assumed_cpu_time_adds_open_question_once():
    plan = add_measurement_question(make_plan())
    assert len(plan.open_questions) == 1 and "20 ms" in plan.open_questions[0]
    assert len(add_measurement_question(plan).open_questions) == 1


def test_customer_given_cpu_time_adds_nothing():
    assert add_measurement_question(make_plan(source="customer")).open_questions == []
