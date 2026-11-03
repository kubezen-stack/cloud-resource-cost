import pytest

from app.schemas.advisor import AdvisorPlan, CapacityInputs
from app.services.capacity import add_measurement_question, check_capacity, check_data_tier, check_plan, check_security, plan_instances, required_peak_vcpu, required_vcpu, size_compute


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


def spiky_capacity(zones=2, rps=1000):
    return CapacityInputs(peak_rps=rps, cpu_ms_per_request=20, target_utilisation=0.6, availability_zones=zones)


def test_planner_covers_peak_and_zone_loss():
    counts = plan_instances(spiky_capacity(), vcpu_per_instance=2)  # A=33.3, B=47.1 -> 48 vCPU
    assert counts.maximum == 24 and counts.minimum == 2


def test_planner_rounds_to_a_multiple_of_the_zones():
    counts = plan_instances(spiky_capacity(zones=3), vcpu_per_instance=3)  # B = 35.3 -> 36 vCPU -> 12 instances
    assert counts.maximum == 12 and counts.maximum % 3 == 0


def test_planner_keeps_a_larger_proposal_and_a_sensible_minimum():
    counts = plan_instances(spiky_capacity(), 2, proposed_min=6, proposed_max=40)
    assert (counts.minimum, counts.maximum) == (6, 40)
    assert plan_instances(spiky_capacity(), 2, proposed_min=1).minimum == 2  # at least one per zone
    assert plan_instances(spiky_capacity(), 2, proposed_min=99).minimum == 24  # never above the maximum
    assert plan_instances(spiky_capacity(), 2, proposed_max=41).maximum == 42  # keeps the zone multiple


def test_planner_ignores_zone_loss_for_a_single_zone():
    counts = plan_instances(spiky_capacity(zones=1), vcpu_per_instance=2)  # only A = 33.3 -> 34 vCPU
    assert counts.maximum == 17


def sized_plan_object(count=2, max_count=2, vcpu=2, zones=2, rps=1000):
    plan = make_plan(count=count, max_count=max_count, vcpu=vcpu, zones=zones)
    plan.capacity.peak_rps = rps
    return plan


def test_size_compute_sets_counts_and_text_consistently():
    plan = sized_plan_object()  # the model proposed 2-2 instances: 4 vCPU for 1000 rps
    findings = size_compute(plan)

    server = plan.components[0]
    assert (server.instance_count, server.max_instances) == (2, 24)
    assert server.sizing == "2-24 x m6i.large (2 vCPU each), auto scaling across 2 Availability Zones"
    assert [f.code for f in findings] == ["sized"] and findings[0].informational
    assert "2-24" in findings[0].message and "proposed 2-2" in findings[0].message
    assert not any(f.blocking for f in check_plan(plan))


def test_size_compute_leaves_counts_alone_when_the_proposal_is_fine_but_rewrites_the_text():
    plan = make_plan(count=4, max_count=6, vcpu=2)  # 200 rps: 12 vCPU is enough
    plan.components[0].sizing = "six big servers"
    assert size_compute(plan) == []
    assert (plan.components[0].instance_count, plan.components[0].max_instances) == (4, 6)
    assert plan.components[0].sizing == "4-6 x m6i.large (2 vCPU each), auto scaling across 2 Availability Zones"


def test_size_compute_fills_in_missing_counts():
    plan = make_plan()
    plan.components[0].instance_count = None
    plan.components[0].max_instances = None
    size_compute(plan)
    assert (plan.components[0].instance_count, plan.components[0].max_instances) == (2, 6)  # 200 rps: ceil(9.41/2)=5 -> 6


def test_size_compute_does_nothing_without_capacity_or_with_several_tiers():
    assert size_compute(make_plan(capacity=False)) == []
    plan = make_plan()
    plan.components.append(plan.components[0].model_copy(update={"name": "worker"}))
    before = [c.model_dump() for c in plan.components]
    assert size_compute(plan) == []
    assert [c.model_dump() for c in plan.components] == before


def test_compute_without_instance_class_is_flagged_even_without_counts():
    plan = make_plan()
    plan.components[0].instance_class = None
    plan.components[0].instance_count = None
    assert [f.code for f in check_data_tier(plan)] == ["missing_size"]
