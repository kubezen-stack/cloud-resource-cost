import logging
from datetime import datetime, timedelta
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.aws_account import AWSaccount
from app.models.cost_anomaly import CostAnomaly
from app.models.user import User
from app.schemas.anomalies import AnomalyDetectResponse, AnomalyItem, AnomalyListResponse
from app.services.anomaly_runner import analyze_account, store_anomalies
from app.services.anomaly_service import Anomaly

logger = logging.getLogger(__name__)

router = APIRouter()

AccountId = Annotated[str, Path(description="AWS Account ID (12 digits)", min_length=12, max_length=12)]

async def _get_account(db: AsyncSession, user: User, aws_account_id: str) -> AWSaccount:
    result = await db.execute(
        select(AWSaccount).where(
            AWSaccount.aws_account_id == aws_account_id,
            AWSaccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AWS account not found")
    return account

def _item_from_detected(anomaly: Anomaly) -> AnomalyItem:
    return AnomalyItem(
        service=anomaly.service,
        date=anomaly.day,
        actual_cost=anomaly.actual_cost,
        expected_cost=anomaly.expected_cost,
        deviation_pct=anomaly.deviation_pct,
        anomaly_score=anomaly.anomaly_score,
    )

def _item_from_row(row: CostAnomaly) -> AnomalyItem:
    return AnomalyItem(
        service=row.service_name,
        date=row.anomaly_date,
        actual_cost=float(row.actual_cost),
        expected_cost=float(row.expected_cost),
        deviation_pct=float(row.deviation_pct) if row.deviation_pct is not None else None,
        anomaly_score=row.anomaly_score,
        detected_at=row.detected_at,
    )

@router.post("/{aws_account_id}/anomalies/detect", response_model=AnomalyDetectResponse)
async def detect_cost_anomalies(
    aws_account_id: AccountId,
    days: Annotated[int, Query(ge=21, le=365, description="How many past days of cost history to analyse")] = 90,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    account = await _get_account(db, current_user, aws_account_id)

    try:
        analysis = await analyze_account(account, days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Anomaly detection failed for account %s", aws_account_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to detect anomalies",
        )

    try:
        now = await store_anomalies(db, account, analysis)
    except Exception:
        logger.exception("Failed to store anomalies for account %s", aws_account_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store anomalies",
        )

    items: List[AnomalyItem] = [_item_from_detected(a) for a in analysis.anomalies]
    for item in items:
        item.detected_at = now

    return AnomalyDetectResponse(
        aws_account_id=aws_account_id,
        start_date=analysis.start_day.isoformat(),
        end_date=analysis.end_day.isoformat(),
        services_analyzed=analysis.services_analyzed,
        anomalies=items,
    )

@router.get("/{aws_account_id}/anomalies", response_model=AnomalyListResponse)
async def list_cost_anomalies(
    aws_account_id: AccountId,
    start_date: Annotated[Optional[str], Query(description="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[Optional[str], Query(description="End date (YYYY-MM-DD), inclusive")] = None,
    service: Annotated[Optional[str], Query(description="Only this AWS service")] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    account = await _get_account(db, current_user, aws_account_id)

    today = datetime.utcnow().date()
    try:
        start_day = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else today - timedelta(days=90)
        end_day = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dates must be in YYYY-MM-DD format",
        )
    if start_day > end_day:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must not be after end_date",
        )

    query = (
        select(CostAnomaly)
        .where(
            CostAnomaly.aws_account_id == account.id,
            CostAnomaly.anomaly_date >= start_day,
            CostAnomaly.anomaly_date <= end_day,
        )
        .order_by(CostAnomaly.anomaly_date.desc(), CostAnomaly.anomaly_score.desc())
    )
    if service:
        query = query.where(CostAnomaly.service_name == service)

    rows = (await db.execute(query)).scalars().all()

    return AnomalyListResponse(
        aws_account_id=aws_account_id,
        start_date=start_day.isoformat(),
        end_date=end_day.isoformat(),
        anomalies=[_item_from_row(r) for r in rows],
    )