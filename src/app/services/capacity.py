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
    informational: bool = False


# After losing one Availability Zone the remaining servers may run hotter than the normal target.
ZONE_LOSS_UTILISATION = 0.85
# Database storage needs room to grow beyond the data the customer has today.
STORAGE_HEADROOM = 1.3


def required_vcpu(capacity: CapacityInputs) -> float:
    """vCPU needed at peak so that average utilisation stays at the target."""
    return capacity.peak_rps * capacity.cpu_ms_per_request / 1000.0 / capacity.target_utilisation


def required_peak_vcpu(capacity: CapacityInputs) -> float:
    """Total vCPU at peak (summed over compute components) that satisfies every capacity check."""
    needed = required_vcpu(capacity)
    zones = capacity.availability_zones
    if zones < 2:
        return needed
    after_loss = capacity.peak_rps * capacity.cpu_ms_per_request / 1000.0 / ZONE_LOSS_UTILISATION
    return max(needed, after_loss * zones / (zones - 1))


def check_capacity(plan: AdvisorPlan) -> List[Finding]:
    compute = [c for c in plan.components if c.role == "compute" and c.instance_count and c.vcpu_per_instance]
    findings: List[Finding] = []
    capacity = plan.capacity

    if capacity is None:
        if compute:
            findings.append(Finding(
                "unverified", "Capacity inputs were not given, so the compute sizing is not verified.", informational=True))
        return findings
    if not compute:
        findings.append(Finding(
            "no_compute", "No compute component has instance_count and vcpu_per_instance, so capacity cannot be verified.",
            informational=True))
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

    zones = capacity.availability_zones
    if zones >= 2:
        needed_after_loss = capacity.peak_rps * capacity.cpu_ms_per_request / 1000.0 / ZONE_LOSS_UTILISATION
        remaining = provisioned * (zones - 1) / zones
        if remaining < needed_after_loss:
            findings.append(Finding(
                "zone_loss",
                f"If one of {zones} Availability Zones fails at peak, about {remaining:.1f} vCPU remain but "
                f"{math.ceil(needed_after_loss * 10) / 10:g} vCPU are needed: raise max_instances or vcpu_per_instance "
                "so that high availability holds at peak load.",
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


def check_data_tier(plan: AdvisorPlan) -> List[Finding]:
    """Databases and caches need a concrete class, databases also storage that fits the data."""
    findings: List[Finding] = []
    for component in plan.components:
        if component.role in ("database", "cache") and not component.instance_class:
            findings.append(Finding(
                "missing_size", f"'{component.name}' has no instance_class (for example db.m6g.large).", blocking=True))
        if component.role == "database":
            if not component.storage_gb:
                findings.append(Finding("missing_size", f"'{component.name}' has no storage_gb.", blocking=True))
            elif plan.capacity and plan.capacity.data_size_gb:
                needed = plan.capacity.data_size_gb * STORAGE_HEADROOM
                if component.storage_gb < needed:
                    findings.append(Finding(
                        "small_storage",
                        f"'{component.name}' has {component.storage_gb} GB storage but the stated data of "
                        f"{plan.capacity.data_size_gb:g} GB needs at least {math.ceil(needed)} GB with growth headroom.",
                        blocking=True,
                    ))
    return findings


def check_security(plan: AdvisorPlan) -> List[Finding]:
    if any(c.role == "security" for c in plan.components):
        return []
    highly_available = bool(plan.capacity and plan.capacity.availability_zones >= 2)
    return [Finding(
        "no_security",
        "No security component (private subnets, security groups, encryption, WAF) is part of the plan.",
        blocking=highly_available,
        informational=not highly_available,
    )]


def check_plan(plan: AdvisorPlan) -> List[Finding]:
    return check_capacity(plan) + check_data_tier(plan) + check_security(plan)


def add_measurement_question(plan: AdvisorPlan) -> AdvisorPlan:
    """CPU time per request estimated by the model must be measured by the customer."""
    capacity = plan.capacity
    if capacity is None:
        return plan
    questions = [q.lower() for q in plan.open_questions]
    if capacity.peak_rps_source == "assumption" and not any("peak traffic" in q for q in questions):
        plan.open_questions.append(
            f"What is the real peak traffic? {capacity.peak_rps:g} requests per second was assumed: "
            "confirm it and the sizing will be recalculated."
        )
    if capacity.cpu_ms_source == "assumption" and not any("cpu" in q and "request" in q for q in questions):
        plan.open_questions.append(
            f"How much CPU time does one request really need? {capacity.cpu_ms_per_request:g} ms was assumed: "
            "measure it with a load test and the sizing will be recalculated."
        )
    return plan
