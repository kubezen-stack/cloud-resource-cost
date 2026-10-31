import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.aws_account import AWSaccount
from app.models.rightsizing_recommendation import RightsizingRecommendation
from app.services.cloudwatch_service import AWSInfraService
from app.services.rightsizing_service import Recommendation, recommend_all

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RightsizingAnalysis:
    regions: List[str]
    days: int
    recommendations: List[Recommendation]


def _collect_and_recommend(account: AWSaccount, regions: List[str], days: int) -> List[Recommendation]:
    service = AWSInfraService(role_arn=account.role_arn, external_id=account.external_id)
    return recommend_all(service.collect_instance_metrics(regions, days))


async def analyze_account(account: AWSaccount, regions: List[str], days: int) -> RightsizingAnalysis:
    recommendations = await run_in_threadpool(_collect_and_recommend, account, regions, days)
    return RightsizingAnalysis(regions, days, recommendations)


async def store_recommendations(db: AsyncSession, account: AWSaccount, analysis: RightsizingAnalysis) -> datetime:
    """Replace the account's stored snapshot; instances that disappeared vanish too."""
    detected_at = datetime.utcnow()
    try:
        await db.execute(
            delete(RightsizingRecommendation).where(
                RightsizingRecommendation.aws_account_id == account.id,
                RightsizingRecommendation.region.in_(analysis.regions),
            )
        )
        for r in analysis.recommendations:
            db.add(RightsizingRecommendation(
                aws_account_id=account.id,
                instance_id=r.instance_id,
                instance_name=r.name,
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
                detected_at=detected_at,
            ))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return detected_at
