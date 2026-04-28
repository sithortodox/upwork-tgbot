import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional, List
from shared.database import get_db
from shared.models_db import User, Filter
from shared.utils import format_list_field, parse_list_field
import structlog

router = APIRouter()
logger = structlog.get_logger()

class FilterCreate(BaseModel):
    name: Optional[str] = "Default"
    categories: Optional[List[str]] = None
    keywords_include: Optional[List[str]] = None
    keywords_exclude: Optional[List[str]] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    is_active: bool = True

class FilterUpdate(BaseModel):
    name: Optional[str] = None
    categories: Optional[List[str]] = None
    keywords_include: Optional[List[str]] = None
    keywords_exclude: Optional[List[str]] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    is_active: Optional[bool] = None

class FilterResponse(BaseModel):
    id: int
    user_id: int
    name: str
    categories: List[str]
    keywords_include: List[str]
    keywords_exclude: List[str]
    budget_min: Optional[float]
    budget_max: Optional[float]
    is_active: bool

class AIFilterRequest(BaseModel):
    command: str

@router.get("/{telegram_id}", response_model=List[FilterResponse])
async def get_filters(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    filter_result = await db.execute(
        select(Filter).where(Filter.user_id == user.id)
    )
    filters = filter_result.scalars().all()
    
    return [
        FilterResponse(
            id=f.id,
            user_id=f.user_id,
            name=f.name,
            categories=parse_list_field(f.categories),
            keywords_include=parse_list_field(f.keywords_include),
            keywords_exclude=parse_list_field(f.keywords_exclude),
            budget_min=f.budget_min,
            budget_max=f.budget_max,
            is_active=f.is_active
        )
        for f in filters
    ]

@router.post("/{telegram_id}", response_model=FilterResponse)
async def create_filter(
    telegram_id: int,
    filter_data: FilterCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_filter = Filter(
        user_id=user.id,
        name=filter_data.name,
        categories=format_list_field(filter_data.categories or []),
        keywords_include=format_list_field(filter_data.keywords_include or []),
        keywords_exclude=format_list_field(filter_data.keywords_exclude or []),
        budget_min=filter_data.budget_min,
        budget_max=filter_data.budget_max,
        is_active=filter_data.is_active
    )
    db.add(new_filter)
    await db.commit()
    await db.refresh(new_filter)
    
    logger.info("filter_created", user_id=user.id, filter_id=new_filter.id)
    
    return FilterResponse(
        id=new_filter.id,
        user_id=new_filter.user_id,
        name=new_filter.name,
        categories=parse_list_field(new_filter.categories),
        keywords_include=parse_list_field(new_filter.keywords_include),
        keywords_exclude=parse_list_field(new_filter.keywords_exclude),
        budget_min=new_filter.budget_min,
        budget_max=new_filter.budget_max,
        is_active=new_filter.is_active
    )

@router.put("/{telegram_id}/{filter_id}", response_model=FilterResponse)
async def update_filter(
    telegram_id: int,
    filter_id: int,
    filter_data: FilterUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    filter_result = await db.execute(
        select(Filter).where(Filter.id == filter_id, Filter.user_id == user.id)
    )
    existing_filter = filter_result.scalar_one_or_none()
    
    if not existing_filter:
        raise HTTPException(status_code=404, detail="Filter not found")
    
    if filter_data.name is not None:
        existing_filter.name = filter_data.name
    if filter_data.categories is not None:
        existing_filter.categories = format_list_field(filter_data.categories)
    if filter_data.keywords_include is not None:
        existing_filter.keywords_include = format_list_field(filter_data.keywords_include)
    if filter_data.keywords_exclude is not None:
        existing_filter.keywords_exclude = format_list_field(filter_data.keywords_exclude)
    if filter_data.budget_min is not None:
        existing_filter.budget_min = filter_data.budget_min
    if filter_data.budget_max is not None:
        existing_filter.budget_max = filter_data.budget_max
    if filter_data.is_active is not None:
        existing_filter.is_active = filter_data.is_active
    
    await db.commit()
    await db.refresh(existing_filter)
    
    logger.info("filter_updated", user_id=user.id, filter_id=filter_id)
    
    return FilterResponse(
        id=existing_filter.id,
        user_id=existing_filter.user_id,
        name=existing_filter.name,
        categories=parse_list_field(existing_filter.categories),
        keywords_include=parse_list_field(existing_filter.keywords_include),
        keywords_exclude=parse_list_field(existing_filter.keywords_exclude),
        budget_min=existing_filter.budget_min,
        budget_max=existing_filter.budget_max,
        is_active=existing_filter.is_active
    )

@router.delete("/{telegram_id}/{filter_id}")
async def delete_filter(
    telegram_id: int,
    filter_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.execute(
        delete(Filter).where(Filter.id == filter_id, Filter.user_id == user.id)
    )
    await db.commit()
    
    logger.info("filter_deleted", user_id=user.id, filter_id=filter_id)
    
    return {"status": "success"}

@router.post("/{telegram_id}/ai-edit", response_model=FilterResponse)
async def ai_edit_filter(
    telegram_id: int,
    request: AIFilterRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    filter_result = await db.execute(
        select(Filter).where(Filter.user_id == user.id, Filter.is_active == True)
    )
    existing_filter = filter_result.scalar_one_or_none()
    
    if not existing_filter:
        existing_filter = Filter(user_id=user.id, name="AI Generated")
        db.add(existing_filter)
    
    existing_filter.categories = '["web development", "python"]'
    
    await db.commit()
    await db.refresh(existing_filter)
    
    logger.info("filter_ai_edited", user_id=user.id)
    
    return FilterResponse(
        id=existing_filter.id,
        user_id=existing_filter.user_id,
        name=existing_filter.name,
        categories=parse_list_field(existing_filter.categories),
        keywords_include=parse_list_field(existing_filter.keywords_include),
        keywords_exclude=parse_list_field(existing_filter.keywords_exclude),
        budget_min=existing_filter.budget_min,
        budget_max=existing_filter.budget_max,
        is_active=existing_filter.is_active
    )
