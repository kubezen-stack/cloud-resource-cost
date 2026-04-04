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

router = APIRouter()

@router.post("/", response_model=AWSAccountResponse, status_code=status.HTTP_201_CREATED, responses={500: {"description": "Database error"}})
async def connect_aws_account(account_data: AWSCreateAccount, 
                              current_user: Annotated[User, Depends(get_current_user)],
                              db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(AWSaccount).where(AWSaccount.role_arn == account_data.role_arn)
    )
    existing_account = result.scalar_one_or_none()

    if existing_account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account already connected")
    
    external_id=f"cost-opt-{str(uuid_pkg.uuid4())[:16]}"

    new_account = AWSaccount(
        user_id=current_user.id,
        aws_account_name=account_data.aws_account_name,
        aws_account_id=account_data.aws_account_id,
        role_arn=account_data.role_arn,
        external_id=external_id
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

@router.get('/{account_id}', response_model=AWSAccountResponse)
async def get_aws_account(account_id: uuid_pkg.UUID, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(AWSaccount).where(AWSaccount.id == account_id).where(AWSaccount.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account