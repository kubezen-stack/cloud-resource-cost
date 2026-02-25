from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True
    )

class User(BaseSchema):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(User):
    password: str

class UserLogin(BaseSchema):
    email: EmailStr
    password: str

class UserResponse(User):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime

class Token(BaseSchema):
    access_token: str
    token_type: str