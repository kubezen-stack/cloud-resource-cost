import boto3
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def validate_aws_role(role_arn: str, external_id: str) -> Tuple[bool, Optional[str]]:
    try:
        sts_client = boto3.client("sts")
        response = sts_client.assume_role(
            RoleArn=role_arn,
            ExternalId=external_id,
            RoleSessionName="cost-optimizer-validation",
            DurationSeconds=900
        )
        credentials = response["Credentials"]

        ce_client = boto3.client(
            "ce",
            region_name="us-east-1",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"]
        )

        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        ce_client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"]
        )

        return True, None

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Role validation failed for {role_arn}: {error_msg}")
        return False, error_msg