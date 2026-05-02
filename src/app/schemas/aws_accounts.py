import uuid
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class AWSAccountBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,   
        str_strip_whitespace=True
    )

    aws_account_name: str = Field(..., min_length=3, max_length=50)
    aws_account_id: str = Field(..., min_length=12, max_length=12)
    role_arn: str = Field(..., pattern="^arn:aws:iam::[0-9]+:role/.+$")

class AWSCreateAccount(AWSAccountBase):
    pass

class AWSAccountResponse(AWSAccountBase):
    id: uuid.UUID
    user_id: uuid.UUID
    external_id: str
    is_active: bool
    last_validated_at: Optional[datetime] = None
    last_validation_error: Optional[str] = None
    created_at: datetime

class ServiceCostItem(BaseModel):
    service: str
    total_cost: float
 
 
class CostGroupItem(BaseModel):
    service: str
    amount: float
    unit: str
 
 
class CostPeriod(BaseModel):
    start: str
    end: str
    total: float
    groups: List[CostGroupItem]
 
 
class CostUsageResponse(BaseModel):
    account_id: uuid.UUID
    aws_account_id: str
    aws_account_name: str
    start_date: str
    end_date: str
    granularity: str
    periods: List[CostPeriod]
 
 
class ForecastPeriod(BaseModel):
    start: str
    end: str
    mean_value: float
    prediction_interval_lower_bound: Optional[float] = None
    prediction_interval_upper_bound: Optional[float] = None
 
 
class CostForecastResponse(BaseModel):
    account_id: uuid.UUID
    aws_account_id: str
    aws_account_name: str
    total_forecast: float
    unit: str
    periods: List[ForecastPeriod]
 
 
class TopServicesResponse(BaseModel):
    account_id: uuid.UUID
    aws_account_id: str
    aws_account_name: str
    start_date: str
    end_date: str
    services: List[ServiceCostItem]
 
 
class SyncCostsResponse(BaseModel):
    account_id: uuid.UUID
    aws_account_id: str
    aws_account_name: str
    synced_records: int
    start_date: str
    end_date: str