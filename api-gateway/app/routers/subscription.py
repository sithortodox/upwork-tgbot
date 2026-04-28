import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from shared.database import get_db
from shared.models_db import User, Payment, NotificationSettings, Plan
from shared.utils import generate_referral_code, calculate_days_left
from app.config import settings
from datetime import datetime, timedelta
import aiohttp
import structlog

router = APIRouter()
logger = structlog.get_logger()

class SubscriptionStatus(BaseModel):
    plan: str
    days_left: int
    generations_today: int
    daily_limit: int

class PaymentRequest(BaseModel):
    method: str
    days: int = 30

class PaymentResponse(BaseModel):
    payment_url: Optional[str]
    payment_id: int

class ReferralResponse(BaseModel):
    referral_code: str
    invited_count: int
    earned_days: int

class NotificationSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    schedule: Optional[str] = None

@router.get("/{telegram_id}/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    daily_limit = settings.FREE_DAILY_AI_LIMIT if user.plan.value == "free" else 999999
    
    return SubscriptionStatus(
        plan=user.plan.value,
        days_left=calculate_days_left(user.plan_expires_at),
        generations_today=user.ai_generations_today,
        daily_limit=daily_limit
    )

@router.post("/{telegram_id}/pay", response_model=PaymentResponse)
async def create_payment(
    telegram_id: int,
    data: PaymentRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    amount = 499 * data.days // 30
    
    payment = Payment(
        user_id=user.id,
        amount=amount,
        currency="RUB",
        method=data.method
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    
    if data.method == "stars":
        return PaymentResponse(
            payment_url=None,
            payment_id=payment.id
        )
    elif data.method == "yookassa":
        async with aiohttp.ClientSession() as session:
            payload = {
                "amount": {"value": str(amount), "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/your_bot"
                },
                "capture": True,
                "description": f"Pro subscription for {data.days} days"
            }
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                auth=aiohttp.BasicAuth(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=500, detail="Payment service error")
                payment_data = await resp.json()
                
                payment.external_id = payment_data["id"]
                await db.commit()
                
                return PaymentResponse(
                    payment_url=payment_data["confirmation"]["confirmation_url"],
                    payment_id=payment.id
                )
    
    raise HTTPException(status_code=400, detail="Invalid payment method")

@router.post("/{telegram_id}/confirm/{payment_id}")
async def confirm_payment(
    telegram_id: int,
    payment_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    payment_result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user.id)
    )
    payment = payment_result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment.status = "completed"
    
    if user.plan == Plan.FREE:
        user.plan = Plan.PRO
        user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
    else:
        if user.plan_expires_at:
            user.plan_expires_at += timedelta(days=30)
        else:
            user.plan_expires_at = datetime.utcnow() + timedelta(days=30)
    
    await db.commit()
    
    logger.info("payment_confirmed", user_id=user.id, payment_id=payment_id)
    
    return {"status": "success", "plan": user.plan.value}

@router.get("/{telegram_id}/referral", response_model=ReferralResponse)
async def get_referral(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    invited_result = await db.execute(
        select(User).where(User.referred_by == user.id)
    )
    invited_users = invited_result.scalars().all()
    
    earned_days = len(invited_users) * 7
    
    return ReferralResponse(
        referral_code=user.referral_code,
        invited_count=len(invited_users),
        earned_days=earned_days
    )

@router.post("/{telegram_id}/apply-referral/{code}")
async def apply_referral(
    telegram_id: int,
    code: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.referred_by:
        raise HTTPException(status_code=400, detail="Already referred")
    
    referrer_result = await db.execute(
        select(User).where(User.referral_code == code)
    )
    referrer = referrer_result.scalar_one_or_none()
    
    if not referrer:
        raise HTTPException(status_code=404, detail="Invalid referral code")
    
    if referrer.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot refer yourself")
    
    user.referred_by = referrer.id
    
    if referrer.plan == Plan.FREE:
        if referrer.plan_expires_at:
            referrer.plan_expires_at += timedelta(days=7)
        else:
            referrer.plan_expires_at = datetime.utcnow() + timedelta(days=7)
        referrer.plan = Plan.PRO
    
    await db.commit()
    
    logger.info("referral_applied", user_id=user.id, referrer_id=referrer.id)
    
    return {"status": "success", "bonus_days": 7}

@router.get("/{telegram_id}/notifications")
async def get_notification_settings(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    settings_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user.id)
    )
    user_settings = settings_result.scalar_one_or_none()
    
    if not user_settings:
        return {"enabled": True, "schedule": "immediate"}
    
    return {
        "enabled": user_settings.enabled,
        "schedule": user_settings.schedule
    }

@router.put("/{telegram_id}/notifications")
async def update_notification_settings(
    telegram_id: int,
    data: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    settings_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user.id)
    )
    user_settings = settings_result.scalar_one_or_none()
    
    if not user_settings:
        user_settings = NotificationSettings(user_id=user.id)
        db.add(user_settings)
    
    if data.enabled is not None:
        user_settings.enabled = data.enabled
    if data.schedule is not None:
        user_settings.schedule = data.schedule
    
    await db.commit()
    
    return {"status": "success"}
