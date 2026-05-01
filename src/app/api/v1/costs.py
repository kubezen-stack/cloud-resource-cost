from typing import Annotated, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid as uuid_pkg

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.aws_account import AWSaccount
from app.models.user import User
from app.services.cost_service import AWSCostService

router = APIRouter()

@router.get("/{aws_account_id}/costs")
async def get_account_costs(
    aws_account_id: Annotated[str, Path(description="AWS Account ID (12 digits)", min_length=12, max_length=12)],
    start_date: Annotated[Optional[str], Query(description="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[Optional[str], Query(description="End date (YYYY-MM-DD)")] = None,
    granularity: Annotated[str, Query(description="DAILY, MONTHLY, or HOURLY")] = "DAILY",
    group_by: Annotated[Optional[str], Query(description="SERVICE, REGION, INSTANCE_TYPE, etc.")] = "SERVICE",
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get cost and usage data for an AWS account"""
    
    result = await db.execute(
        select(AWSaccount).where(
            AWSaccount.aws_account_id == aws_account_id,
            AWSaccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AWS account not found"
        )
    
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    try:
        cost_service = AWSCostService(
            role_arn=account.role_arn,
            external_id=account.external_id
        )
        
        group_by_param = [{'Type': 'DIMENSION', 'Key': group_by}] if group_by else None
        
        costs = cost_service.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            group_by=group_by_param
        )
        
        return {
            "aws_account_id": aws_account_id,
            "account_name": account.aws_account_name,
            "start_date": start_date,
            "end_date": end_date,
            "granularity": granularity,
            "results": costs
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch costs: {str(e)}"
        )
    
@router.get("/{aws_account_id}/forecast")
async def get_cost_forecast(
    aws_account_id: Annotated[str, Path(description="AWS Account ID (12 digits)", min_length=12, max_length=12)],
    start_date: Annotated[Optional[str], Query(description="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[Optional[str], Query(description="End date (YYYY-MM-DD)")] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get cost forecast for an AWS account"""
    
    result = await db.execute(
        select(AWSaccount).where(
            AWSaccount.aws_account_id == aws_account_id,
            AWSaccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AWS account not found"
        )
    
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    
    try:
        cost_service = AWSCostService(
            role_arn=account.role_arn,
            external_id=account.external_id
        )
        
        forecast = cost_service.get_cost_forecast(
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "aws_account_id": aws_account_id,
            "account_name": account.aws_account_name,
            "start_date": start_date,
            "end_date": end_date,
            "forecast": forecast
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch forecast: {str(e)}"
        )

@router.get("/{aws_account_id}/breakdown")
async def get_cost_breakdown(
    aws_account_id: Annotated[str, Path(description="AWS Account ID (12 digits)", min_length=12, max_length=12)],
    start_date: Annotated[Optional[str], Query()] = None,
    end_date: Annotated[Optional[str], Query()] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Get cost breakdown by service for an AWS account"""
    
    result = await db.execute(
        select(AWSaccount).where(
            AWSaccount.aws_account_id == aws_account_id,
            AWSaccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AWS account not found"
        )
    
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    
    try:
        cost_service = AWSCostService(
            role_arn=account.role_arn,
            external_id=account.external_id
        )
        
        costs = cost_service.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity="MONTHLY",
            group_by=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )
        
        service_costs = {}
        for time_period in costs:
            for group in time_period.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                
                if service in service_costs:
                    service_costs[service] += amount
                else:
                    service_costs[service] = amount
        
        sorted_services = sorted(
            service_costs.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "aws_account_id": aws_account_id,
            "account_name": account.aws_account_name,
            "period": f"{start_date} to {end_date}",
            "breakdown": [
                {"service": service, "cost": cost}
                for service, cost in sorted_services
            ],
            "total": sum(service_costs.values())
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch breakdown: {str(e)}"
        )