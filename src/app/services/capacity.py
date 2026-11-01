"""Deterministic checks of an advisor plan. The model proposes, this code verifies."""
import math
from dataclasses import dataclass
from typing import List

from app.schemas.advisor import AdvisorPlan, CapacityInputs


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    blocking: bool = False


def required_vcpu(capacity: CapacityInputs) -> float:
    """vCPU needed at peak so that average utilisation stays at the target."""
    return capacity.peak_rps * capacity.cpu_ms_per_request / 1000.0 / capacity.target_utilisation


def check_capacity(plan: AdvisorPlan) -> List[Finding]:
    compute = [c for c in plan.components if c.role == "compute" and c.instance_count and c.vcpu_per_instance]
    findings: List[Finding] = []
    capacity = plan.capacity

    if capacity is None:
        if compute:
            findings.append(Finding("unverified", "Capacity inputs were not given, so the compute sizing is not verified."))
        return findings
    if not compute:
        findings.append(Finding(
            "no_compute", "No compute component has instance_count and vcpu_per_instance, so capacity cannot be verified."))
        return findings

    needed = required_vcpu(capacity)
    provisioned = sum((c.max_instances or c.instance_count) * c.vcpu_per_instance for c in compute)
    if provisioned < needed:
        findings.append(Finding(
            "shortfall",
            f"Peak compute capacity is {provisioned} vCPU but {math.ceil(needed * 10) / 10:g} vCPU are needed for "
            f"{capacity.peak_rps:g} rps at {capacity.cpu_ms_per_request:g} ms CPU per request and "
            f"{capacity.target_utilisation:.0%} target utilisation.",
            blocking=True,
        ))

    for component in compute:
        if component.instance_count < capacity.availability_zones:
            findings.append(Finding(
                "few_instances",
                f"'{component.name}' starts with {component.instance_count} instance(s) but spans "
                f"{capacity.availability_zones} Availability Zones: use at least one per zone.",
                blocking=True,
            ))
        if component.max_instances is None:
            findings.append(Finding("no_max", f"'{component.name}' has no max_instances, so auto scaling has no upper bound."))
        elif component.max_instances < component.instance_count:
            findings.append(Finding(
                "bad_max", f"'{component.name}' has max_instances below instance_count.", blocking=True))
    return findings


def add_measurement_question(plan: AdvisorPlan) -> AdvisorPlan:
    """CPU time per request estimated by the model must be measured by the customer."""
    capacity = plan.capacity
    if capacity is None or capacity.cpu_ms_source != "assumption":
        return plan
    if any("cpu" in q.lower() and "request" in q.lower() for q in plan.open_questions):
        return plan
    plan.open_questions.append(
        f"How much CPU time does one request really need? {capacity.cpu_ms_per_request:g} ms was assumed: "
        "measure it with a load test and the sizing will be recalculated."
    )
    return plan
