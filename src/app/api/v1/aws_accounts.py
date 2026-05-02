from datetime import datetime, timezone
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
import uuid as uuid_pkg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.aws_account import AWSaccount
from app.models.user import User
from app.schemas.aws_accounts import AWSAccountResponse, AWSCreateAccount
from app.services.aws_validation_service import validate_aws_role

router = APIRouter()

@router.post("/", response_model=AWSAccountResponse, status_code=status.HTTP_201_CREATED, responses={500: {"description": "Database error"}})
async def connect_aws_account(account_data: AWSCreateAccount,
                              current_user: Annotated[User, Depends(get_current_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(AWSaccount).where(AWSaccount.role_arn == account_data.role_arn)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This role ARN is already connected"
        )

    result = await db.execute(
        select(AWSaccount).where(
            AWSaccount.user_id == current_user.id,
            AWSaccount.aws_account_id == account_data.aws_account_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AWS account {account_data.aws_account_id} is already connected"
        )

    external_id = f"cost-opt-{str(uuid_pkg.uuid4())[:16]}"

    is_valid, error = validate_aws_role(account_data.role_arn, external_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assume role: {error}"
        )

    new_account = AWSaccount(
        user_id=current_user.id,
        aws_account_name=account_data.aws_account_name,
        aws_account_id=account_data.aws_account_id,
        role_arn=account_data.role_arn,
        external_id=external_id,
        last_validated_at=datetime.now(timezone.utc),
        last_validation_error=None
    )
    db.add(new_account)

    try:
        await db.commit()
        await db.refresh(new_account)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    return new_account

@router.get('/', response_model=List[AWSAccountResponse])
async def get_aws_accounts(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(AWSaccount).where(AWSaccount.user_id == current_user.id).order_by(AWSaccount.created_at.desc())
    )
    accounts = result.scalars().all()
    return accounts

@router.get('/{aws_account_id}', response_model=AWSAccountResponse)
async def get_aws_account(
    aws_account_id: str, 
    current_user: Annotated[User, Depends(get_current_user)], 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(AWSaccount).where(
            AWSaccount.aws_account_id == aws_account_id,
            AWSaccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account