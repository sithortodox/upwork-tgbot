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
from app.services.upwork_oauth import upwork_oauth
import structlog

router = APIRouter()
logger = structlog.get_logger()

class AuthCallback(BaseModel):
    code: str
    state: Optional[str] = None

class ProxyUpdate(BaseModel):
    proxy_url: Optional[str] = None

@router.get("/url/{user_id}")
async def get_auth_url(user_id: int):
    auth_url = upwork_oauth.generate_auth_url(user_id)
    return {"auth_url": auth_url}

@router.post("/callback/{user_id}")
async def auth_callback(
    user_id: int,
    data: AuthCallback,
    db: AsyncSession = Depends(get_db)
):
    if data.state:
        validated_user_id = upwork_oauth.validate_state(data.state)
        if not validated_user_id or validated_user_id != user_id:
            raise HTTPException(status_code=400, detail="Invalid state")
    
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
    
    token_data = await upwork_oauth.exchange_code(data.code)
    
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code")
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    if not user_session:
        user_session = UserSession(user_id=user.id)
        db.add(user_session)
    
    user_session.access_token = token_data.get("access_token")
    user_session.refresh_token = token_data.get("refresh_token")
    
    expires_in = token_data.get("expires_in", 86400)
    user_session.token_expires_at = upwork_oauth.calculate_expires_at(expires_in)
    
    if "user_id" in token_data:
        user_session.upwork_user_id = token_data["user_id"]
    
    await db.commit()
    
    logger.info("user_authenticated", user_id=user.id, has_token=bool(user_session.access_token))
    return {"status": "success", "user_id": user.id}

@router.post("/refresh/{user_id}")
async def refresh_auth(
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
    
    if not user_session or not user_session.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token")
    
    token_data = await upwork_oauth.refresh_token(user_session.refresh_token)
    
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to refresh token")
    
    user_session.access_token = token_data.get("access_token")
    if token_data.get("refresh_token"):
        user_session.refresh_token = token_data["refresh_token"]
    
    expires_in = token_data.get("expires_in", 86400)
    user_session.token_expires_at = upwork_oauth.calculate_expires_at(expires_in)
    
    await db.commit()
    
    return {"status": "success"}

@router.get("/status/{user_id}")
async def get_auth_status(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"authenticated": False, "has_session": False}
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    if not user_session or not user_session.access_token:
        return {"authenticated": False, "has_session": False}
    
    from datetime import datetime
    is_expired = user_session.token_expires_at and user_session.token_expires_at < datetime.utcnow()
    
    return {
        "authenticated": not is_expired,
        "has_session": True,
        "expires_at": user_session.token_expires_at.isoformat() if user_session.token_expires_at else None,
        "upwork_user_id": user_session.upwork_user_id
    }

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
