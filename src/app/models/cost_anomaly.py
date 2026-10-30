from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime

class CostAnomaly(Base):
    __tablename__ = "cost_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    aws_account_id = Column(UUID(as_uuid=True), ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False)
    service_name = Column(String, nullable=False)
    anomaly_date = Column(Date, nullable=False)
    actual_cost = Column(Numeric(12, 2), nullable=False)
    expected_cost = Column(Numeric(12, 2), nullable=False)
    deviation_pct = Column(Numeric(12, 2), nullable=True)
    anomaly_score = Column(Float, nullable=False)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("aws_account_id", "service_name", "anomaly_date", name="uq_cost_anomaly_account_service_date"),
        Index("ix_cost_anomalies_account_date", "aws_account_id", "anomaly_date"),
    )
