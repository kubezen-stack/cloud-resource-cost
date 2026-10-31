import datetime
import logging
from typing import Dict, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.services.cost_service import AWSCostService
from app.services.rightsizing_service import InstanceMetrics

logger = logging.getLogger(__name__)

# get_metric_data accepts at most 500 queries per call; two per instance.
QUERIES_PER_CALL = 500
PERIOD_SECONDS = 3600


class AWSInfraService(AWSCostService):
    def _regional_client(self, service: str, region: str):
        credentials = self._get_credentials()
        return boto3.client(
            service,
            region_name=region,
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            config=Config(retries={"max_attempts": 3}),
        )

    def _running_instances(self, region: str) -> List[Dict]:
        ec2 = self._regional_client("ec2", region)
        instances = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running"]}]):
            for reservation in page.get("Reservations", []):
                for item in reservation.get("Instances", []):
                    tags = {t["Key"]: t["Value"] for t in item.get("Tags", [])}
                    instances.append({
                        "id": item["InstanceId"],
                        "type": item["InstanceType"],
                        "name": tags.get("Name"),
                    })
        return instances

    def _cpu_history(self, region: str, instance_ids: List[str], days: int) -> Dict[str, Dict[str, List[float]]]:
        cloudwatch = self._regional_client("cloudwatch", region)
        end = datetime.datetime.now(datetime.UTC)
        start = end - datetime.timedelta(days=days)

        history: Dict[str, Dict[str, List[float]]] = {i: {"avg": [], "max": []} for i in instance_ids}
        queries = []
        for index, instance_id in enumerate(instance_ids):
            for prefix, stat in (("a", "Average"), ("m", "Maximum")):
                queries.append({
                    "Id": f"{prefix}{index}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EC2",
                            "MetricName": "CPUUtilization",
                            "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                        },
                        "Period": PERIOD_SECONDS,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                })

        for offset in range(0, len(queries), QUERIES_PER_CALL):
            batch = queries[offset:offset + QUERIES_PER_CALL]
            token: Optional[str] = None
            while True:
                kwargs = {"MetricDataQueries": batch, "StartTime": start, "EndTime": end}
                if token:
                    kwargs["NextToken"] = token
                response = cloudwatch.get_metric_data(**kwargs)
                for series in response.get("MetricDataResults", []):
                    index = int(series["Id"][1:])
                    key = "avg" if series["Id"].startswith("a") else "max"
                    history[instance_ids[index]][key].extend(series.get("Values", []))
                token = response.get("NextToken")
                if not token:
                    break
        return history

    def collect_instance_metrics(self, regions: List[str], days: int = 14) -> List[InstanceMetrics]:
        collected: List[InstanceMetrics] = []
        for region in regions:
            try:
                instances = self._running_instances(region)
                history = self._cpu_history(region, [i["id"] for i in instances], days) if instances else {}
            except ClientError as e:
                logger.exception("Failed to collect EC2/CloudWatch data in %s", region)
                code = e.response.get("Error", {}).get("Code", "")
                hint = " (the role needs ec2:DescribeInstances and cloudwatch:GetMetricData)" if "Denied" in code or "Unauthorized" in code else ""
                raise ValueError(f"Failed to collect instance metrics in {region}: {e}{hint}")
            for instance in instances:
                data = history[instance["id"]]
                collected.append(InstanceMetrics(
                    instance_id=instance["id"],
                    name=instance["name"],
                    instance_type=instance["type"],
                    region=region,
                    hourly_avg=data["avg"],
                    hourly_max=data["max"],
                ))
        return collected
