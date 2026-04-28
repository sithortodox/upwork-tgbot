import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from shared.database import get_db
from shared.models_db import User, AIPrompt, Project
from shared.utils import reset_daily_if_needed
from app.config import settings
from datetime import datetime
import aiohttp
import structlog

router = APIRouter()
logger = structlog.get_logger()

class AIGenerateRequest(BaseModel):
    project_id: int
    additional_context: Optional[str] = None

class AIGenerateResponse(BaseModel):
    cover_letter: str
    generations_left: int

class PromptUpdate(BaseModel):
    prompt: str

class StyleImportRequest(BaseModel):
    text: str

class LimitsResponse(BaseModel):
    daily_limit: int
    used_today: int
    plan: str

@router.post("/{telegram_id}/generate", response_model=AIGenerateResponse)
async def generate_cover_letter(
    telegram_id: int,
    request: AIGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if reset_daily_if_needed(user.ai_last_reset):
        user.ai_generations_today = 0
        user.ai_last_reset = datetime.utcnow()
    
    if user.plan.value == "free" and user.ai_generations_today >= settings.FREE_DAILY_AI_LIMIT:
        raise HTTPException(status_code=403, detail="Daily limit exceeded")
    
    project_result = await db.execute(
        select(Project).where(Project.id == request.project_id)
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    prompt_result = await db.execute(
        select(AIPrompt).where(AIPrompt.user_id == user.id)
    )
    user_prompt = prompt_result.scalar_one_or_none()
    
    async with aiohttp.ClientSession() as session:
        payload = {
            "user_id": user.id,
            "project_title": project.title,
            "project_description": project.description,
            "additional_context": request.additional_context,
            "system_prompt": user_prompt.system_prompt if user_prompt else None,
            "style_example": user_prompt.style_example if user_prompt else None
        }
        
        async with session.post(
            f"{settings.AI_SERVICE_URL}/generate",
            json=payload
        ) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=500, detail="AI service error")
            data = await resp.json()
    
    user.ai_generations_today += 1
    await db.commit()
    
    logger.info("cover_letter_generated", user_id=user.id, project_id=request.project_id)
    
    daily_limit = settings.FREE_DAILY_AI_LIMIT if user.plan.value == "free" else 999999
    
    return AIGenerateResponse(
        cover_letter=data["cover_letter"],
        generations_left=daily_limit - user.ai_generations_today
    )

@router.get("/{telegram_id}/prompt")
async def get_prompt(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    prompt_result = await db.execute(
        select(AIPrompt).where(AIPrompt.user_id == user.id)
    )
    user_prompt = prompt_result.scalar_one_or_none()
    
    if not user_prompt:
        return {"prompt": "", "style_example": None}
    
    return {
        "prompt": user_prompt.system_prompt,
        "style_example": user_prompt.style_example
    }

@router.put("/{telegram_id}/prompt")
async def update_prompt(
    telegram_id: int,
    data: PromptUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    prompt_result = await db.execute(
        select(AIPrompt).where(AIPrompt.user_id == user.id)
    )
    user_prompt = prompt_result.scalar_one_or_none()
    
    if not user_prompt:
        user_prompt = AIPrompt(user_id=user.id, system_prompt=data.prompt)
        db.add(user_prompt)
    else:
        user_prompt.system_prompt = data.prompt
    
    await db.commit()
    
    logger.info("prompt_updated", user_id=user.id)
    
    return {"status": "success"}

@router.post("/{telegram_id}/import-style")
async def import_style(
    telegram_id: int,
    data: StyleImportRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    prompt_result = await db.execute(
        select(AIPrompt).where(AIPrompt.user_id == user.id)
    )
    user_prompt = prompt_result.scalar_one_or_none()
    
    if not user_prompt:
        user_prompt = AIPrompt(user_id=user.id, style_example=data.text)
        db.add(user_prompt)
    else:
        user_prompt.style_example = data.text
    
    await db.commit()
    
    logger.info("style_imported", user_id=user.id)
    
    return {"status": "success"}

@router.get("/{telegram_id}/limits", response_model=LimitsResponse)
async def get_limits(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if reset_daily_if_needed(user.ai_last_reset):
        user.ai_generations_today = 0
        user.ai_last_reset = datetime.utcnow()
        await db.commit()
    
    daily_limit = settings.FREE_DAILY_AI_LIMIT if user.plan.value == "free" else 999999
    
    return LimitsResponse(
        daily_limit=daily_limit,
        used_today=user.ai_generations_today,
        plan=user.plan.value
    )
