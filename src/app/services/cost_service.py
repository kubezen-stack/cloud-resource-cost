import datetime
from typing import Dict, List, Optional
import boto3
import logging

logger = logging.getLogger(__name__)

class AWSCostService:
    def __init__(self, role_arn: str, external_id: str):
        self.role_arn = role_arn
        self.external_id = external_id
        self._credentials = None
        self._expiry_credentials = None

    def _get_credentials(self) -> Dict:
        """Get temporary credentials by assuming IAM role"""
        if self._credentials and self._expiry_credentials:
            now = datetime.datetime.now(datetime.timezone.utc)
            if now < self._expiry_credentials - datetime.timedelta(minutes=5):
                return self._credentials
        try:
            sts_client = boto3.client("sts")
            response = sts_client.assume_role(
                RoleArn=self.role_arn, 
                ExternalId=self.external_id, 
                RoleSessionName="cost-optimizer", 
                DurationSeconds=3600
            )
            self._credentials = response["Credentials"]
            self._expiry_credentials = response["Credentials"]["Expiration"]
            return self._credentials
        except Exception as e:
            logger.exception(f"Failed to get credentials for role {self.role_arn}: {str(e)}")
            raise ValueError(f"Failed to authenticate with AWS: {str(e)}")

    def _get_cost_explorer_client(self):
        """Get AWS Cost Explorer client with assumed role credentials"""
        credentials = self._get_credentials()
        return boto3.client(
            "ce", 
            region_name="us-east-1", 
            aws_access_key_id=credentials["AccessKeyId"], 
            aws_secret_access_key=credentials["SecretAccessKey"], 
            aws_session_token=credentials["SessionToken"]
        )

    def get_cost_and_usage(
        self, 
        start_date: str, 
        end_date: str, 
        granularity: str = "DAILY", 
        metrics: Optional[List[str]] = None, 
        group_by: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Get cost and usage data from AWS Cost Explorer"""
        client = self._get_cost_explorer_client()

        if metrics is None:
            metrics = ['UnblendedCost', 'UsageQuantity']

        if group_by is None:
            group_by = [{'Type': 'DIMENSION', 'Key': 'SERVICE'}]

        try:
            response = client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity=granularity,
                GroupBy=group_by,
                Metrics=metrics
            )
            return response["ResultsByTime"]
        except Exception as e:
            logger.exception(f"Failed to get cost data: {str(e)}")
            raise ValueError(f"Failed to fetch AWS costs: {str(e)}")

    def get_cost_forecast(
        self, 
        start_date: str, 
        end_date: str, 
        metrics: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get cost forecast from AWS Cost Explorer"""
        try:
            client = self._get_cost_explorer_client()

            if metrics is None:
                metrics = ['UNBLENDED_COST']

            response = client.get_cost_forecast(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metric=metrics[0]
            )
            return response.get("ForecastResultsByTime", [])
        except Exception as e:
            logger.exception(f"Failed to get cost forecast: {str(e)}")
            raise ValueError(f"Failed to fetch cost forecast: {str(e)}")