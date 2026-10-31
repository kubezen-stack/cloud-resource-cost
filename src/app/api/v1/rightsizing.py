import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.aws_account import AWSaccount
from app.models.rightsizing_recommendation import RightsizingRecommendation
from app.models.user import User
from app.schemas.rightsizing import (
    RecommendationItem,
    RightsizingDetectResponse,
    RightsizingListResponse,
)
from app.services.rightsizing_runner import analyze_account, store_recommendations
from app.services.rightsizing_service import ACTIONS, Recommendation

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


def _item_from_recommendation(r: Recommendation) -> RecommendationItem:
    return RecommendationItem(
        instance_id=r.instance_id,
        name=r.name,
        region=r.region,
        instance_type=r.instance_type,
        action=r.action,
        recommended_type=r.recommended_type,
        estimated_savings_pct=r.estimated_savings_pct,
        cpu_avg=r.cpu_avg,
        cpu_p95=r.cpu_p95,
        cpu_max=r.cpu_max,
        hours_observed=r.hours_observed,
        reason=r.reason,
    )


def _item_from_row(row: RightsizingRecommendation) -> RecommendationItem:
    return RecommendationItem(
        instance_id=row.instance_id,
        name=row.instance_name,
        region=row.region,
        instance_type=row.instance_type,
        action=row.action,
        recommended_type=row.recommended_type,
        estimated_savings_pct=float(row.estimated_savings_pct) if row.estimated_savings_pct is not None else None,
        cpu_avg=row.cpu_avg,
        cpu_p95=row.cpu_p95,
        cpu_max=row.cpu_max,
        hours_observed=row.hours_observed,
        reason=row.reason,
        detected_at=row.detected_at,
    )


@router.post("/{aws_account_id}/rightsizing/detect", response_model=RightsizingDetectResponse)
async def detect_rightsizing(
    aws_account_id: AccountId,
    regions: Annotated[List[str], Query(description="AWS regions to scan")] = ["us-east-1"],
    days: Annotated[int, Query(ge=7, le=30, description="Days of CPU history")] = 14,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    account = await _get_account(db, current_user, aws_account_id)

    try:
        analysis = await analyze_account(account, regions, days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Rightsizing failed for account %s", aws_account_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyse instances",
        )

    try:
        detected_at = await store_recommendations(db, account, analysis)
    except Exception:
        logger.exception("Failed to store rightsizing for account %s", aws_account_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store recommendations",
        )

    items = [_item_from_recommendation(r) for r in analysis.recommendations]
    for item in items:
        item.detected_at = detected_at

    return RightsizingDetectResponse(
        aws_account_id=aws_account_id,
        regions=regions,
        days=days,
        instances_analyzed=len(items),
        recommendations=items,
    )


@router.get("/{aws_account_id}/rightsizing", response_model=RightsizingListResponse)
async def list_rightsizing(
    aws_account_id: AccountId,
    action: Annotated[Optional[str], Query(description=f"Only this action: {', '.join(ACTIONS)}")] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    account = await _get_account(db, current_user, aws_account_id)

    if action is not None and action not in ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"action must be one of: {', '.join(ACTIONS)}",
        )

    query = (
        select(RightsizingRecommendation)
        .where(RightsizingRecommendation.aws_account_id == account.id)
        .order_by(RightsizingRecommendation.estimated_savings_pct.desc().nullslast(), RightsizingRecommendation.instance_id)
    )
    if action:
        query = query.where(RightsizingRecommendation.action == action)

    rows = (await db.execute(query)).scalars().all()
    return RightsizingListResponse(
        aws_account_id=aws_account_id,
        recommendations=[_item_from_row(r) for r in rows],
    )
