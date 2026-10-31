import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.aws_account import AWSaccount
from app.models.cost_anomaly import CostAnomaly
from app.services.anomaly_service import Anomaly, detect_anomalies
from app.services.cost_service import AWSCostService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisResult:
    start_day: date
    end_day: date
    services_analyzed: int
    anomalies: List[Anomaly]


def _fetch_daily_costs_by_service(account: AWSaccount, start: str, end: str) -> list:
    cost_service = AWSCostService(role_arn=account.role_arn, external_id=account.external_id)
    return cost_service.get_cost_and_usage(
        start_date=start,
        end_date=end,
        granularity="DAILY",
        group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )


async def analyze_account(account: AWSaccount, days: int) -> AnalysisResult:
    end_day = datetime.utcnow().date()
    start_day = end_day - timedelta(days=days)

    results = await run_in_threadpool(
        _fetch_daily_costs_by_service, account, start_day.isoformat(), end_day.isoformat()
    )
    anomalies = await run_in_threadpool(detect_anomalies, results)

    services_analyzed = len({
        key
        for period in results
        for group in period.get("Groups", [])
        for key in group.get("Keys", [])[:1]
    })
    return AnalysisResult(start_day, end_day, services_analyzed, anomalies)


async def store_anomalies(db: AsyncSession, account: AWSaccount, result: AnalysisResult) -> datetime:
    detected_at = datetime.utcnow()
    try:
        await db.execute(
            delete(CostAnomaly).where(
                CostAnomaly.aws_account_id == account.id,
                CostAnomaly.anomaly_date >= result.start_day,
                CostAnomaly.anomaly_date < result.end_day,
            )
        )
        for a in result.anomalies:
            db.add(CostAnomaly(
                aws_account_id=account.id,
                service_name=a.service,
                anomaly_date=a.day,
                actual_cost=a.actual_cost,
                expected_cost=a.expected_cost,
                deviation_pct=a.deviation_pct,
                anomaly_score=a.anomaly_score,
                detected_at=detected_at,
            ))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return detected_at
