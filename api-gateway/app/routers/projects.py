import sys
sys.path.insert(0, '/app')

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from shared.database import get_db
from shared.models_db import User, Project, SeenProject, Filter
from shared.utils import parse_list_field
from app.config import settings
import aiohttp
import structlog

router = APIRouter()
logger = structlog.get_logger()

class ProjectResponse(BaseModel):
    id: int
    external_id: str
    title: str
    description: str
    budget_min: Optional[float]
    budget_max: Optional[float]
    category: Optional[str]
    url: str
    is_new: bool = True

class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int

@router.get("/{telegram_id}", response_model=ProjectListResponse)
async def get_projects(
    telegram_id: int,
    limit: int = 10,
    offset: int = 0,
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
    user_filter = filter_result.scalar_one_or_none()
    
    async with aiohttp.ClientSession() as session:
        params = {"limit": limit, "offset": offset}
        if user_filter:
            params["categories"] = user_filter.categories
            params["keywords_include"] = user_filter.keywords_include
            params["keywords_exclude"] = user_filter.keywords_exclude
            params["budget_min"] = user_filter.budget_min or ""
            params["budget_max"] = user_filter.budget_max or ""
        
        async with session.get(
            f"{settings.PARSER_SERVICE_URL}/projects",
            params=params
        ) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=500, detail="Parser service error")
            data = await resp.json()
    
    seen_result = await db.execute(
        select(SeenProject.project_id).where(SeenProject.user_id == user.id)
    )
    seen_ids = set(row[0] for row in seen_result.fetchall())
    
    projects = []
    for p in data.get("projects", []):
        project_result = await db.execute(
            select(Project).where(Project.external_id == p["external_id"])
        )
        project = project_result.scalar_one_or_none()
        
        if project:
            projects.append(ProjectResponse(
                id=project.id,
                external_id=project.external_id,
                title=project.title,
                description=project.description[:500] + "..." if len(project.description) > 500 else project.description,
                budget_min=project.budget_min,
                budget_max=project.budget_max,
                category=project.category,
                url=project.url,
                is_new=project.id not in seen_ids
            ))
    
    return ProjectListResponse(projects=projects, total=len(projects))

@router.post("/{telegram_id}/seen/{project_id}")
async def mark_project_seen(
    telegram_id: int,
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    seen = SeenProject(user_id=user.id, project_id=project_id)
    db.add(seen)
    await db.commit()
    
    return {"status": "success"}

@router.get("/{telegram_id}/project/{project_id}", response_model=ProjectResponse)
async def get_project_detail(
    telegram_id: int,
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    is_new = True
    if user:
        seen_result = await db.execute(
            select(SeenProject).where(
                SeenProject.user_id == user.id,
                SeenProject.project_id == project.id
            )
        )
        is_new = seen_result.scalar_one_or_none() is None
    
    return ProjectResponse(
        id=project.id,
        external_id=project.external_id,
        title=project.title,
        description=project.description,
        budget_min=project.budget_min,
        budget_max=project.budget_max,
        category=project.category,
        url=project.url,
        is_new=is_new
    )
