import pytest

from app.schemas.advisor import AdvisorPlan, CapacityInputs
from app.services.capacity import add_measurement_question, check_capacity, check_data_tier, check_plan, check_security, required_peak_vcpu, required_vcpu


def make_plan(count=4, max_count=6, vcpu=2, capacity=True, source="assumption", zones=2, questions=None, data_gb=None):
    return AdvisorPlan.model_validate({
        "summary": "s",
        "capacity": {"peak_rps": 200, "peak_rps_source": "customer", "cpu_ms_per_request": 20, "cpu_ms_source": source,
                     "target_utilisation": 0.6, "availability_zones": zones, "data_size_gb": data_gb} if capacity else None,
        "components": [{"name": "app", "aws_service": "EC2", "sizing": "x", "rationale": "r", "role": "compute", "instance_class": "m6i.large",
                        "instance_count": count, "max_instances": max_count, "vcpu_per_instance": vcpu},
                       {"name": "sec", "aws_service": "VPC", "sizing": "x", "rationale": "r", "role": "security"}],
        "open_questions": questions or [],
    })


def codes(plan):
    return {f.code for f in check_capacity(plan)}


def test_required_vcpu_formula():
    assert required_vcpu(CapacityInputs(peak_rps=200, cpu_ms_per_request=20, target_utilisation=0.6)) == pytest.approx(6.6667, abs=1e-3)


def test_enough_capacity_passes():
    assert check_capacity(make_plan(count=2, max_count=6, vcpu=2)) == []  # peak 12 vCPU >= 6.67, 6 left after a zone loss


def test_shortfall_is_blocking():
    findings = check_capacity(make_plan(count=2, max_count=2, vcpu=2))  # 4 vCPU < 6.67
    assert findings[0].code == "shortfall" and findings[0].blocking


def test_autoscaling_maximum_counts_for_peak():
    assert "shortfall" not in codes(make_plan(count=2, max_count=6, vcpu=2))


def test_fewer_instances_than_zones_is_blocking():
    findings = check_capacity(make_plan(count=1, max_count=8, vcpu=2, zones=2))
    assert any(f.code == "few_instances" and f.blocking for f in findings)


def test_missing_max_is_only_a_warning():
    findings = check_capacity(make_plan(count=4, max_count=None, vcpu=4))
    assert [f.code for f in findings] == ["no_max"] and not findings[0].blocking


def test_max_below_count_is_blocking():
    assert any(f.code == "bad_max" and f.blocking for f in check_capacity(make_plan(count=4, max_count=2, vcpu=4)))


def test_no_capacity_inputs_is_flagged():
    findings = check_capacity(make_plan(capacity=False))
    assert [f.code for f in findings] == ["unverified"] and findings[0].informational


def test_compute_without_sizes_cannot_be_verified():
    plan = make_plan()
    plan.components[0].vcpu_per_instance = None
    findings = check_capacity(plan)
    assert [f.code for f in findings] == ["no_compute"] and findings[0].informational


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


def test_zone_loss_is_blocking_when_remaining_capacity_is_too_small():
    findings = check_capacity(make_plan(count=2, max_count=4, vcpu=2))
    assert [f.code for f in findings] == ["zone_loss"] and findings[0].blocking


def test_zone_loss_not_checked_for_single_zone():
    assert check_capacity(make_plan(count=1, max_count=4, vcpu=2, zones=1)) == []


def data_plan(zones=2, **database):
    component = {"name": "db", "aws_service": "RDS", "sizing": "x", "rationale": "r", "role": "database",
                 "multi_az": True, "backup_retention_days": 7, **database}
    return AdvisorPlan.model_validate({
        "summary": "s", "capacity": {"peak_rps": 1, "cpu_ms_per_request": 1, "data_size_gb": 50, "availability_zones": zones},
        "components": [component, {"name": "cache", "aws_service": "ElastiCache", "sizing": "x", "rationale": "r",
                                   "role": "cache", "instance_class": "cache.t4g.medium", "replicas": 1}]})


def test_database_without_class_and_storage_is_flagged():
    findings = check_data_tier(data_plan())
    assert len(findings) == 2 and all(f.code == "missing_size" and f.blocking for f in findings)


def test_cache_without_class_is_flagged():
    plan = data_plan(instance_class="db.m6g.large", storage_gb=100)
    plan.components[1].instance_class = None
    assert [f.code for f in check_data_tier(plan)] == ["missing_size"]


def test_storage_must_cover_data_with_headroom():
    findings = check_data_tier(data_plan(instance_class="db.m6g.large", storage_gb=60))  # 50 * 1.3 = 65
    assert [f.code for f in findings] == ["small_storage"] and "65" in findings[0].message
    assert check_data_tier(data_plan(instance_class="db.m6g.large", storage_gb=100)) == []


def test_missing_security_is_blocking_only_for_multi_zone_plans():
    plan = make_plan()
    plan.components = [c for c in plan.components if c.role != "security"]
    assert check_security(plan)[0].blocking
    plan.capacity = None
    finding = check_security(plan)[0]
    assert finding.informational and not finding.blocking
    assert check_security(make_plan()) == []


def test_check_plan_combines_all_checks():
    assert check_plan(make_plan()) == []


def test_required_peak_vcpu_covers_zone_loss():
    capacity = CapacityInputs(peak_rps=200, cpu_ms_per_request=20, target_utilisation=0.6, availability_zones=2)
    assert required_peak_vcpu(capacity) == pytest.approx(2 * 200 * 0.02 / 0.85, abs=1e-6)  # 9.41
    single = CapacityInputs(peak_rps=200, cpu_ms_per_request=20, target_utilisation=0.6, availability_zones=1)
    assert required_peak_vcpu(single) == pytest.approx(required_vcpu(single))


def test_assumed_peak_traffic_adds_open_question_once():
    plan = make_plan(source="customer")
    plan.capacity.peak_rps_source = "assumption"
    plan = add_measurement_question(plan)
    assert len(plan.open_questions) == 1 and "peak traffic" in plan.open_questions[0]
    assert len(add_measurement_question(plan).open_questions) == 1


def test_compute_without_instance_class_is_flagged():
    plan = make_plan()
    plan.components[0].instance_class = None
    findings = check_data_tier(plan)
    assert [f.code for f in findings] == ["missing_size"] and "m6i.large" in findings[0].message


def test_database_needs_multi_az_and_cache_needs_replicas():
    plan = data_plan(instance_class="db.m6g.large", storage_gb=100)
    plan.components[0].multi_az = None
    plan.components[1].replicas = None
    messages = [f.message for f in check_data_tier(plan)]
    assert any("multi_az" in m for m in messages) and any("replicas" in m for m in messages)


def test_database_needs_backup_retention():
    plan = data_plan(instance_class="db.m6g.large", storage_gb=100)
    plan.components[0].backup_retention_days = None
    findings = check_data_tier(plan)
    assert [f.code for f in findings] == ["no_backups"] and findings[0].blocking


def test_single_cache_node_is_not_highly_available():
    plan = data_plan(instance_class="db.m6g.large", storage_gb=100)
    plan.components[1].replicas = 0
    assert [f.code for f in check_data_tier(plan)] == ["cache_not_ha"]
    single_zone = data_plan(zones=1, instance_class="db.m6g.large", storage_gb=100)
    single_zone.components[1].replicas = 0
    assert check_data_tier(single_zone) == []
