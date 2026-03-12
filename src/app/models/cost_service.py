from tkinter import CASCADE

from sqlalchemy import Boolean, Column, ForeignKey, Index, Numeric, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime

class CostService(Base):
    __tablename__ = "cost_services"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    aws_account_id = Column(UUID(as_uuid=True), ForeignKey("aws_accounts.id", ondelete=CASCADE), nullable=False)
    service_name = Column(String, nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
    usage_quantity = Column(Numeric, nullable=True)
    usage_unit = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cost_services_aws_account_account_date", "aws_account_id", "recorded_at"),
        Index("ix_cost_services_service_name", "service_name"),
        Index("ix_cost_records_date", "recorded_at")
    )