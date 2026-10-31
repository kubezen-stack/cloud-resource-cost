from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class RecommendationItem(BaseModel):
    instance_id: str
    name: Optional[str] = None
    region: str
    instance_type: str
    action: str
    recommended_type: Optional[str] = None
    estimated_savings_pct: Optional[float] = None
    cpu_avg: Optional[float] = None
    cpu_p95: Optional[float] = None
    cpu_max: Optional[float] = None
    hours_observed: int
    reason: str
    detected_at: Optional[datetime] = None


class RightsizingDetectResponse(BaseModel):
    aws_account_id: str
    regions: List[str]
    days: int
    instances_analyzed: int
    recommendations: List[RecommendationItem]
    note: str = "Based on CPU only: memory is not available in default CloudWatch metrics."


class RightsizingListResponse(BaseModel):
    aws_account_id: str
    recommendations: List[RecommendationItem]
