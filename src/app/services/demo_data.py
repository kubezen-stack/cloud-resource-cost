from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app.services.anomaly_advice import load_playbook
from app.services.anomaly_explain import Driver
from app.services.anomaly_service import Anomaly

Key = Tuple[str, str]  # (usage type, region)

REGION = "us-east-1"

# service -> usage type -> typical cost of one day, in dollars
BILL: Dict[str, Dict[str, float]] = {
    "Amazon Elastic Compute Cloud - Compute": {"USE1-BoxUsage:t3.medium": 2.00},
    "EC2 - Other": {
        "USE1-NatGateway-Hours": 1.08,
        "USE1-NatGateway-Bytes": 0.45,
        "EBS:VolumeUsage.gp3": 0.16,
        "USE1-DataTransfer-Regional-Bytes": 0.08,
    },
    "Amazon Relational Database Service": {
        "USE1-InstanceUsage:db.t3.small": 0.82,
        "USE1-RDS:GP2-Storage": 0.12,
    },
    "Amazon Simple Storage Service": {
        "USE1-TimedStorage-ByteHrs": 0.05,
        "USE1-Requests-Tier1": 0.02,
    },
    "AWS Secrets Manager": {"USE1-AWSSecretsManager-Secrets": 0.07},
}

# The usage type that spikes, and by how much.
SPIKE_SERVICE = "EC2 - Other"
SPIKE_USAGE_TYPE = "USE1-NatGateway-Bytes"
SPIKE_FACTOR = 60.0


def _day(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _amount(value: float) -> dict:
    return {"UnblendedCost": {"Amount": f"{value:.10f}", "Unit": "USD"}}


class DemoCostExplorer:
    """Stands in for boto3.client("ce"): get_cost_and_usage for the queries the alert job makes."""

    def __init__(self, spike_day: date, seed: str = "demo"):
        self.spike_day = spike_day
        self.seed = seed

    def cost(self, service: str, usage_type: str, day: date) -> float:
        base = BILL[service][usage_type]
        noise = random.Random(f"{self.seed}|{usage_type}|{day}").gauss(1.0, 0.04)
        spiked = day == self.spike_day and usage_type == SPIKE_USAGE_TYPE
        return base * max(noise, 0.5) * (SPIKE_FACTOR if spiked else 1.0)

    def get_cost_and_usage(self, **params) -> dict:
        start, end = _day(params["TimePeriod"]["Start"]), _day(params["TimePeriod"]["End"])
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        services = self._services(params.get("Filter"))
        group_keys = [g["Key"] for g in params.get("GroupBy", [])]
        if params.get("Granularity") == "DAILY":
            periods = [([d], d, d + timedelta(days=1)) for d in days]
        else:
            periods = [(days, start, end)]
        return {"ResultsByTime": [self._period(d, s, e, services, group_keys) for d, s, e in periods]}

    @staticmethod
    def _services(filter_: Optional[dict]) -> List[str]:
        if filter_ and "Dimensions" in filter_ and filter_["Dimensions"]["Key"] == "SERVICE":
            return [s for s in filter_["Dimensions"]["Values"] if s in BILL]
        return list(BILL)

    def _period(self, days: List[date], start: date, end: date, services: List[str], group_keys: List[str]) -> dict:
        totals: Dict[Tuple[str, ...], float] = {}
        for service in services:
            for usage_type in BILL[service]:
                key = tuple(service if k == "SERVICE" else usage_type if k == "USAGE_TYPE" else REGION
                            for k in group_keys)
                totals[key] = totals.get(key, 0.0) + sum(self.cost(service, usage_type, d) for d in days)
        period = {"TimePeriod": {"Start": str(start), "End": str(end)}, "Estimated": False}
        if group_keys:
            period["Total"] = {}
            period["Groups"] = [{"Keys": list(k), "Metrics": _amount(v)} for k, v in totals.items()]
        else:
            period["Total"] = _amount(sum(totals.values()))
            period["Groups"] = []
        return period


CAUSES: Dict[str, dict] = {
    "data processed by a nat gateway": {
        "hypotheses": [
            ("A workload started moving much more traffic through the NAT Gateway, for example image pulls, "
             "package downloads or a backup job sending data out.",
             "In CloudWatch open the NAT Gateway metrics BytesOutToDestination and BytesOutToSource, then use "
             "VPC Flow Logs on the gateway network interface to find the biggest destinations."),
            ("A new or changed deployment now reaches AWS services such as S3 or ECR over the internet "
             "instead of through a VPC endpoint.",
             "Look in CloudTrail for deployments around that day and check where the traffic goes."),
        ],
        "actions": [
            "Find which instance and which destination send the most data through the NAT Gateway.",
            "If the traffic goes to S3 or ECR, add a VPC endpoint so it no longer passes the NAT Gateway.",
        ],
        "expected_if": "This is expected if a deployment, a data migration or a large backup ran that day.",
        "questions": ["Did a deployment or a data migration run on that day?"],
    },
}


class DemoAdviceClient:
    """An LLMClient that writes advice from the facts, so the demo needs no API key.

    The answer is built from the same drivers the real model would see, so it passes the same checks.
    """
    model = "demo"
    embedding_model = "demo"

    def __init__(self, anomaly: Anomaly, drivers: List[Driver]):
        self.anomaly = anomaly
        self.drivers = drivers

    async def complete_json(self, system: str, user: str) -> str:
        top = self.drivers[0]
        playbook = load_playbook()
        heading = next((h for h in playbook if top.meaning and h.lower() == top.meaning.lower()), None)
        known = CAUSES.get((top.meaning or "").lower())
        if known:
            hypotheses = [{"cause": c, "evidence": [top.usage_type], "how_to_check": h} for c, h in known["hypotheses"]]
            actions, expected_if, questions = known["actions"], known["expected_if"], known["questions"]
        else:
            hypotheses = [{
                "cause": f"A workload that uses {top.usage_type} grew, for example after a deployment or more traffic.",
                "evidence": [top.usage_type],
                "how_to_check": "Open Cost Explorer for this usage type and compare it with the days before.",
            }]
            actions = [f"Find the resources that use {top.usage_type} and check what changed on that day."]
            expected_if = "This is expected if a deployment, a launch or a migration happened that day."
            questions = ["Was a change planned for that day?"]
        return json.dumps({
            "summary": (f"{self.anomaly.service} cost ${self.anomaly.actual_cost:.2f} instead of "
                        f"${self.anomaly.expected_cost:.2f}, mostly from {top.usage_type}."),
            "hypotheses": hypotheses,
            "actions": [{"step": a, "source": heading if i == 0 else None} for i, a in enumerate(actions)],
            "expected_if": expected_if,
            "questions": questions,
        })

    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("The demo advice client does not embed text")

    async def aclose(self) -> None:
        return None
