import uuid
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional
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
    created_at: datetime