import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from shared.database import get_db
from shared.models_db import User, UserSession
from shared.utils import generate_referral_code
import structlog

router = APIRouter()
logger = structlog.get_logger()

class AuthCallback(BaseModel):
    code: str
    state: Optional[str] = None

class ProxyUpdate(BaseModel):
    proxy_url: Optional[str] = None

@router.post("/callback/{user_id}")
async def auth_callback(
    user_id: int,
    data: AuthCallback,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=user_id,
            referral_code=generate_referral_code()
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    session = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session.scalar_one_or_none()
    
    if not user_session:
        user_session = UserSession(user_id=user.id)
        db.add(user_session)
    
    user_session.access_token = data.code
    await db.commit()
    
    logger.info("user_authenticated", user_id=user.id)
    return {"status": "success", "user_id": user.id}

@router.post("/proxy/{user_id}")
async def set_proxy(
    user_id: int,
    data: ProxyUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    if not user_session:
        user_session = UserSession(user_id=user.id)
        db.add(user_session)
    
    user_session.proxy_url = data.proxy_url
    await db.commit()
    
    return {"status": "success"}

@router.delete("/{user_id}")
async def unlink_account(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    if user_session:
        await db.delete(user_session)
    
    await db.commit()
    
    logger.info("account_unlinked", user_id=user.id)
    return {"status": "success"}
