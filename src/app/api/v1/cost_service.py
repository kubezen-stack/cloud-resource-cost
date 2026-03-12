import datetime
from typing import Dict, List, Optional

import boto3
import logging

logger = logging.getLogger(__name__)

class AWSCostService:
    def __init__ (self, role_arn, external_id):
        self.role_arn = role_arn
        self.external_id = external_id
        self._credintials = None
        self._expiry_credintials = None

    def _get_credintials(self) -> Dict:
        if self._credintials and self._expiry_credintials:
            if datetime.now() < self._expiry_credintials - datetime.timedelta(minutes=5):
                return self._credintials
            
        try:
            sts_client = boto3.client("sts")
            self._credintials = sts_client.assume_role(RoleArn=self.role_arn, 
                                                       ExternalId=self.external_id, 
                                                       RoleSessionName="cost-opt", 
                                                       DurationSeconds=3600)
            self._expiry_credintials = datetime.now() + datetime.timedelta(seconds=self._credintials["Credentials"]["Expiration"].timestamp() - datetime.now().timestamp())
            return self._credintials
        except:
            logger.exception(f"Failed to get credintials for role {self.role_arn}: {str(e)}")
            raise ValueError(f"Failed to authenticate with AWS: {str(e)}")
        
    def _get_cost_explorer_client(self):
        credintials = self._get_credintials()
        return boto3.client("ce", 
                            region_name="us-east-1", 
                            aws_access_key_id=credintials["Credentials"]["AccessKeyId"], 
                            aws_secret_access_key=credintials["Credentials"]["SecretAccessKey"], 
                            aws_session_token=credintials["Credentials"]["SessionToken"]
                        )
    
    def get_cost_and_usage(self, start_date: str, end_date: str, granularity: str = "DAILY", metrics: Optional[List[str]] = None, group_by: Optional[List[Dict]] = None) -> List[Dict]:
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

    def forecost_client_cost(self, start_date: str, end_date: str, metrics: Optional[List[str]] = None) -> List[Dict]:
        try:
            client = self._get_cost_explorer_client()
            response = client.forecost_client_cost(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=metrics
            )
            return response["ResultsByTime"]
        except Exception as e:
            logger.exception(f"Failed to get cost forecast: {str(e)}")
            raise ValueError(f"Failed to fetch cost forecast: {str(e)}")