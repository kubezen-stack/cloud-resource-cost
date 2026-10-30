from datetime import date as date_type, datetime
from typing import List, Optional
from pydantic import BaseModel

class AnomalyItem(BaseModel):
    service: str
    date: date_type
    actual_cost: float
    expected_cost: float
    deviation_pct: Optional[float] = None
    anomaly_score: float
    detected_at: Optional[datetime] = None

class AnomalyDetectResponse(BaseModel):
    aws_account_id: str
    start_date: str
    end_date: str
    services_analyzed: int
    anomalies: List[AnomalyItem]

class AnomalyListResponse(BaseModel):
    aws_account_id: str
    start_date: str
    end_date: str
    anomalies: List[AnomalyItem]