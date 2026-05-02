from sqlalchemy import Boolean, Column, ForeignKey, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime

class AWSaccount(Base):
    __tablename__ = "aws_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    aws_account_name = Column(String, nullable=False)
    aws_account_id = Column(String, nullable=False)
    role_arn = Column(String, nullable=False, unique=True)
    external_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_validated_at = Column(DateTime, nullable=True)
    last_validation_error = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'aws_account_id', name='uq_user_aws_account'),
    )