import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from shared.database import get_db
from shared.models_db import User, UserSession
from shared.utils import generate_referral_code
from shared.crypto import crypto_service
from app.config import settings
import structlog
import json
import httpx

router = APIRouter()
logger = structlog.get_logger()

class AuthCallback(BaseModel):
    code: str
    state: Optional[str] = None

class ProxyUpdate(BaseModel):
    proxy_url: Optional[str] = None

class CredentialsLogin(BaseModel):
    email: str
    password: str
    totp_secret: Optional[str] = None

class CookiesUpdate(BaseModel):
    cookies: str

@router.post("/credentials/{user_id}")
async def login_with_credentials(
    user_id: int,
    data: CredentialsLogin,
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
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    if not user_session:
        user_session = UserSession(user_id=user.id)
        db.add(user_session)
    
    user_session.upwork_email = data.email
    user_session.upwork_password_encrypted = crypto_service.encrypt(data.password)
    if data.totp_secret:
        user_session.upwork_2fa_secret = crypto_service.encrypt(data.totp_secret)
    user_session.login_status = "pending"
    
    await db.commit()
    
    logger.info("credentials_saved", user_id=user.id)
    return {"status": "success", "message": "Credentials saved. Login will be processed."}

@router.post("/cookies/{user_id}")
async def update_cookies(
    user_id: int,
    data: CookiesUpdate,
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
    
    user_session.cookies = data.cookies
    user_session.cookies_updated_at = datetime.utcnow()
    user_session.login_status = "active"
    
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
        return {"authenticated": False, "has_session": False, "status": "not_registered"}
    
    session_result = await db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    )
    user_session = session_result.scalar_one_or_none()
    
    if not user_session:
        return {"authenticated": False, "has_session": False, "status": "not_configured"}
    
    has_cookies = bool(user_session.cookies)
    has_credentials = bool(user_session.upwork_email and user_session.upwork_password_encrypted)
    
    login_status = user_session.login_status or "not_configured"
    
    return {
        "authenticated": has_cookies,
        "has_session": has_cookies or has_credentials,
        "status": login_status,
        "has_credentials": has_credentials,
        "email": user_session.upwork_email,
        "has_2fa": bool(user_session.upwork_2fa_secret),
        "cookies_updated": user_session.cookies_updated_at.isoformat() if user_session.cookies_updated_at else None
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

@router.post("/login/{user_id}")
async def trigger_login(user_id: int):
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(
                f"{settings.PARSER_SERVICE_URL}/auth/login/{user_id}",
                timeout=180.0
            )
            return response.json()
        except Exception as e:
            logger.error("login_trigger_error", error=str(e))
            return {"status": "error", "message": str(e)}
