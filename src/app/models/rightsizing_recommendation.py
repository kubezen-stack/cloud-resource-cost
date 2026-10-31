from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime


class RightsizingRecommendation(Base):
    __tablename__ = "rightsizing_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    aws_account_id = Column(UUID(as_uuid=True), ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False)
    instance_id = Column(String, nullable=False)
    instance_name = Column(String, nullable=True)
    region = Column(String, nullable=False)
    instance_type = Column(String, nullable=False)
    action = Column(String, nullable=False)
    recommended_type = Column(String, nullable=True)
    estimated_savings_pct = Column(Numeric(5, 1), nullable=True)
    cpu_avg = Column(Float, nullable=True)
    cpu_p95 = Column(Float, nullable=True)
    cpu_max = Column(Float, nullable=True)
    hours_observed = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("aws_account_id", "instance_id", name="uq_rightsizing_account_instance"),
        Index("ix_rightsizing_account_action", "aws_account_id", "action"),
    )
