import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.advisor import AdvisorPlan


class CostRequest(BaseModel):
    plan: AdvisorPlan
    region: str = Field(default="eu-central-1", description="AWS region the plan will run in")

    @field_validator("region")
    @classmethod
    def region_looks_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", value):
            raise ValueError("region must look like eu-central-1")
        return value


class CostLine(BaseModel):
    component: str
    item: str
    quantity: float
    unit: str
    unit_price_usd: float
    monthly_usd: float
    sku: Optional[str] = None
    assumed: bool = False
    note: Optional[str] = None


class UsageItem(BaseModel):
    """A charge that depends on real usage: not part of the fixed total."""
    component: str
    item: str
    depends_on: str
    unit_price_usd: Optional[float] = None
    unit: Optional[str] = None


class Alternative(BaseModel):
    key: str
    title: str
    monthly_usd: float
    saving_usd: float
    saving_pct: float
    caveats: List[str] = Field(default_factory=list)
    lines: List[CostLine]


class CostEstimate(BaseModel):
    region: str
    prices_as_of: str
    hours_per_month: int
    lines: List[CostLine]
    # Steady state: compute at instance_count. Upper bound: every compute instance at max_instances all month.
    fixed_monthly_usd: float
    upper_bound_monthly_usd: float
    usage_based: List[UsageItem]
    unpriced: List[str]
    alternatives: List[Alternative]
    notes: List[str]
