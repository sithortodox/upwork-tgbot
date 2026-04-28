import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from shared.database import get_db
from shared.models_db import User, Plan
from shared.utils import generate_referral_code, calculate_days_left
import structlog

router = APIRouter()
logger = structlog.get_logger()

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    plan: str
    plan_days_left: int
    ai_generations_today: int
    referral_code: str

class UserStatus(BaseModel):
    exists: bool
    has_session: bool
    plan: str

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == user_data.telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        return UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            plan=user.plan.value,
            plan_days_left=calculate_days_left(user.plan_expires_at),
            ai_generations_today=user.ai_generations_today,
            referral_code=user.referral_code
        )
    
    user = User(
        telegram_id=user_data.telegram_id,
        username=user_data.username,
        referral_code=generate_referral_code()
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info("user_created", user_id=user.id, telegram_id=user.telegram_id)
    
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        plan=user.plan.value,
        plan_days_left=0,
        ai_generations_today=0,
        referral_code=user.referral_code
    )

@router.get("/status/{telegram_id}", response_model=UserStatus)
async def get_user_status(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    from shared.models_db import UserSession
    
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return UserStatus(exists=False, has_session=False, plan="free")
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    return UserStatus(
        exists=True,
        has_session=user_session is not None and user_session.access_token is not None,
        plan=user.plan.value
    )

@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        plan=user.plan.value,
        plan_days_left=calculate_days_left(user.plan_expires_at),
        ai_generations_today=user.ai_generations_today,
        referral_code=user.referral_code
    )
