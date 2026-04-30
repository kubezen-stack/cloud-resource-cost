import datetime
from typing import Dict, List, Optional
import boto3
from botocore.config import Config
import logging
import threading

logger = logging.getLogger(__name__)

class AWSCostService:
    def __init__(self, role_arn: str, external_id: str):
        self.role_arn = role_arn
        self.external_id = external_id
        self._credentials = None
        self._expiry_credentials = None
        self._client = None
        self._lock = threading.Lock()

    def _is_credentials_valid(self) -> bool:
        """Check if credentials are still valid (with 5-minute buffer)"""
        if not self._credentials or not self._expiry_credentials:
            return False
        try:
            now = datetime.datetime.now(datetime.UTC)
            expiry = self._expiry_credentials.replace(tzinfo=datetime.UTC) if self._expiry_credentials.tzinfo is None else self._expiry_credentials
            return now < expiry - datetime.timedelta(minutes=5)
        except (AttributeError, TypeError):
            return False

    def _get_credentials(self) -> Dict:
        """Get temporary credentials by assuming IAM role (thread-safe)"""
        if self._is_credentials_valid():
            return self._credentials
        
        with self._lock:
            if self._is_credentials_valid():
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
        """Get cached AWS Cost Explorer client with assumed role credentials"""
        if self._client is not None and self._is_credentials_valid():
            return self._client
        
        credentials = self._get_credentials()
        config = Config(
            max_pool_connections=25,
            retries={'max_attempts': 3}
        )
        self._client = boto3.client(
            "ce", 
            region_name="us-east-1", 
            aws_access_key_id=credentials["AccessKeyId"], 
            aws_secret_access_key=credentials["SecretAccessKey"], 
            aws_session_token=credentials["SessionToken"],
            config=config
        )
        return self._client

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
            metrics = ['UnblendedCost']

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
        except self._client.exceptions as e:
            if "ExpiredToken" in str(e):
                self._client = None
                self._credentials = None
                self._expiry_credentials = None
                return self.get_cost_and_usage(start_date, end_date, granularity, metrics, group_by)
            logger.exception(f"Failed to get cost data: {str(e)}")
            raise ValueError(f"Failed to fetch AWS costs: {str(e)}")
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