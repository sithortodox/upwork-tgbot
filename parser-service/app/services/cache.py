import sys
sys.path.insert(0, '/app')

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
from shared.database import async_session
from shared.models_db import Project
from shared.utils import parse_list_field
from sqlalchemy import select, and_, or_
from app.config import settings
import structlog

logger = structlog.get_logger()

class CacheService:
    CACHE_PREFIX = "upwork:projects"
    CATEGORIES_KEY = "upwork:categories"
    LAST_UPDATE_KEY = "upwork:last_update"
    
    @staticmethod
    def get_redis():
        return redis.from_url(settings.REDIS_URL)
    
    @staticmethod
    async def get_projects(
        limit: int = 20,
        offset: int = 0,
        categories: str = None,
        keywords_include: str = None,
        keywords_exclude: str = None,
        budget_min: float = None,
        budget_max: float = None
    ) -> Dict[str, Any]:
        
        async with async_session() as db:
            query = select(Project).order_by(Project.created_at.desc())
            
            conditions = []
            
            if categories:
                cat_list = json.loads(categories) if categories.startswith("[") else [categories]
                category_conditions = [
                    Project.category.ilike(f"%{cat}%") for cat in cat_list
                ]
                conditions.append(or_(*category_conditions))
            
            if keywords_include:
                kw_list = json.loads(keywords_include) if keywords_include.startswith("[") else [keywords_include]
                for kw in kw_list:
                    conditions.append(
                        or_(
                            Project.title.ilike(f"%{kw}%"),
                            Project.description.ilike(f"%{kw}%")
                        )
                    )
            
            if keywords_exclude:
                kw_exclude_list = json.loads(keywords_exclude) if keywords_exclude.startswith("[") else [keywords_exclude]
                for kw in kw_exclude_list:
                    query = query.where(
                        and_(
                            Project.title.not_ilike(f"%{kw}%"),
                            Project.description.not_ilike(f"%{kw}%")
                        )
                    )
            
            if budget_min is not None:
                conditions.append(
                    or_(
                        Project.budget_min >= budget_min,
                        and_(Project.budget_min.is_(None), Project.budget_max >= budget_min)
                    )
                )
            
            if budget_max is not None:
                conditions.append(
                    or_(
                        Project.budget_max <= budget_max,
                        and_(Project.budget_max.is_(None), Project.budget_min <= budget_max)
                    )
                )
            
            if conditions:
                query = query.where(and_(*conditions))
            
            count_query = select(Project)
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            result = await db.execute(query.offset(offset).limit(limit))
            projects = result.scalars().all()
            
            total_result = await db.execute(count_query)
            total = len(total_result.scalars().all())
            
            return {
                "projects": [
                    {
                        "id": p.id,
                        "external_id": p.external_id,
                        "title": p.title,
                        "description": p.description[:500] + "..." if len(p.description) > 500 else p.description,
                        "budget_min": p.budget_min,
                        "budget_max": p.budget_max,
                        "budget_type": p.budget_type,
                        "category": p.category,
                        "skills": parse_list_field(p.skills),
                        "url": p.url,
                        "posted_at": p.posted_at.isoformat() if p.posted_at else None
                    }
                    for p in projects
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
    
    @staticmethod
    async def get_project_by_id(project_id: str) -> Optional[Dict]:
        async with async_session() as db:
            result = await db.execute(
                select(Project).where(
                    or_(Project.external_id == project_id, Project.id == int(project_id) if project_id.isdigit() else None)
                )
            )
            project = result.scalar_one_or_none()
            
            if not project:
                return None
            
            return {
                "id": project.id,
                "external_id": project.external_id,
                "title": project.title,
                "description": project.description,
                "budget_min": project.budget_min,
                "budget_max": project.budget_max,
                "budget_type": project.budget_type,
                "category": project.category,
                "skills": parse_list_field(project.skills),
                "url": project.url,
                "posted_at": project.posted_at.isoformat() if project.posted_at else None
            }
    
    @staticmethod
    async def get_categories() -> List[Dict]:
        redis_client = await CacheService.get_redis()
        
        cached = await redis_client.get(CacheService.CATEGORIES_KEY)
        if cached:
            await redis_client.close()
            return json.loads(cached)
        
        async with async_session() as db:
            result = await db.execute(select(Project.category).distinct())
            categories = [{"name": c, "count": 0} for c in result.scalars().all() if c]
        
        await redis_client.setex(
            CacheService.CATEGORIES_KEY,
            3600,
            json.dumps(categories)
        )
        await redis_client.close()
        
        return categories
    
    @staticmethod
    async def update_cache(redis_client):
        await redis_client.setex(
            CacheService.LAST_UPDATE_KEY,
            3600,
            datetime.utcnow().isoformat()
        )
        
        async with async_session() as db:
            result = await db.execute(
                select(Project).order_by(Project.created_at.desc()).limit(100)
            )
            recent_projects = result.scalars().all()
            
            for p in recent_projects:
                key = f"{CacheService.CACHE_PREFIX}:{p.external_id}"
                await redis_client.setex(
                    key,
                    86400,
                    json.dumps({
                        "id": p.id,
                        "external_id": p.external_id,
                        "title": p.title,
                        "description": p.description,
                        "budget_min": p.budget_min,
                        "budget_max": p.budget_max,
                        "category": p.category,
                        "url": p.url
                    })
                )
    
    @staticmethod
    async def get_new_projects_for_user(user_id: int, last_check: datetime) -> List[Dict]:
        async with async_session() as db:
            from shared.models_db import SeenProject
            
            seen_subquery = select(SeenProject.project_id).where(SeenProject.user_id == user_id)
            
            result = await db.execute(
                select(Project).where(
                    and_(
                        Project.created_at > last_check,
                        Project.id.not_in(seen_subquery)
                    )
                ).order_by(Project.created_at.desc()).limit(50)
            )
            projects = result.scalars().all()
            
            return [
                {
                    "id": p.id,
                    "external_id": p.external_id,
                    "title": p.title,
                    "description": p.description[:300],
                    "budget_min": p.budget_min,
                    "budget_max": p.budget_max,
                    "url": p.url
                }
                for p in projects
            ]
