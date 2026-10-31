from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.cloudwatch_service import AWSInfraService


def _service():
    service = AWSInfraService(role_arn="arn:aws:iam::123456789012:role/R", external_id="ext")
    service._get_credentials = lambda: {"AccessKeyId": "a", "SecretAccessKey": "s", "SessionToken": "t"}
    return service


def _clients(ec2, cloudwatch):
    def factory(name, **kwargs):
        return {"ec2": ec2, "cloudwatch": cloudwatch}[name]
    return factory


def _ec2(instances):
    ec2 = MagicMock()
    ec2.get_paginator.return_value.paginate.return_value = [
        {"Reservations": [{"Instances": instances}]}
    ]
    return ec2


def test_collects_instances_with_cpu_history():
    ec2 = _ec2([
        {"InstanceId": "i-1", "InstanceType": "m5.large", "Tags": [{"Key": "Name", "Value": "web"}]},
        {"InstanceId": "i-2", "InstanceType": "t3.micro"},
    ])
    cloudwatch = MagicMock()
    cloudwatch.get_metric_data.return_value = {
        "MetricDataResults": [
            {"Id": "a0", "Values": [10.0, 20.0]}, {"Id": "m0", "Values": [30.0, 40.0]},
            {"Id": "a1", "Values": [1.0]}, {"Id": "m1", "Values": [2.0]},
        ]
    }
    with patch("app.services.cloudwatch_service.boto3.client", side_effect=_clients(ec2, cloudwatch)):
        result = _service().collect_instance_metrics(["us-east-1"], days=14)

    assert [(m.instance_id, m.name, m.instance_type, m.region) for m in result] == [
        ("i-1", "web", "m5.large", "us-east-1"),
        ("i-2", None, "t3.micro", "us-east-1"),
    ]
    assert result[0].hourly_avg == [10.0, 20.0]
    assert result[0].hourly_max == [30.0, 40.0]
    assert result[1].hourly_avg == [1.0]


def test_no_instances_skips_cloudwatch():
    ec2 = _ec2([])
    cloudwatch = MagicMock()
    with patch("app.services.cloudwatch_service.boto3.client", side_effect=_clients(ec2, cloudwatch)):
        assert _service().collect_instance_metrics(["us-east-1"]) == []
    cloudwatch.get_metric_data.assert_not_called()


def test_follows_next_token():
    ec2 = _ec2([{"InstanceId": "i-1", "InstanceType": "m5.large"}])
    cloudwatch = MagicMock()
    cloudwatch.get_metric_data.side_effect = [
        {"MetricDataResults": [{"Id": "a0", "Values": [1.0]}, {"Id": "m0", "Values": [2.0]}], "NextToken": "n"},
        {"MetricDataResults": [{"Id": "a0", "Values": [3.0]}, {"Id": "m0", "Values": [4.0]}]},
    ]
    with patch("app.services.cloudwatch_service.boto3.client", side_effect=_clients(ec2, cloudwatch)):
        result = _service().collect_instance_metrics(["us-east-1"])

    assert cloudwatch.get_metric_data.call_count == 2
    assert result[0].hourly_avg == [1.0, 3.0]


def test_access_denied_explains_missing_permissions():
    ec2 = MagicMock()
    ec2.get_paginator.return_value.paginate.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "nope"}}, "DescribeInstances"
    )
    with patch("app.services.cloudwatch_service.boto3.client", side_effect=_clients(ec2, MagicMock())):
        with pytest.raises(ValueError, match="ec2:DescribeInstances and cloudwatch:GetMetricData"):
            _service().collect_instance_metrics(["us-east-1"])
