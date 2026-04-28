import sys
sys.path.insert(0, '/app')

import aiohttp
import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
import re
import structlog
from app.config import settings
from shared.database import async_session
from shared.models_db import Project, UserSession
from shared.utils import format_list_field, parse_list_field
from app.services.cache import CacheService
from sqlalchemy import select
import redis.asyncio as redis

logger = structlog.get_logger()

class UpworkService:
    BASE_URL = "https://www.upwork.com"
    API_URL = "https://www.upwork.com/ab/find-work/api"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.upwork.com",
        "Referer": "https://www.upwork.com/",
    }
    
    CATEGORIES = {
        "web-dev": "Web Development",
        "mobile-dev": "Mobile Development",
        "design": "Design & Creative",
        "writing": "Writing",
        "admin": "Admin Support",
        "data": "Data Science & Analytics",
        "it": "IT & Networking",
        "engineering": "Engineering & Architecture",
        "sales": "Sales & Marketing",
        "legal": "Legal",
        "finance": "Accounting & Consulting"
    }
    
    @staticmethod
    async def fetch_and_store_projects():
        logger.info("starting_project_fetch")
        
        redis_client = redis.from_url(settings.REDIS_URL)
        
        try:
            projects = []
            
            tasks = [
                UpworkService._fetch_category_jobs(category, redis_client)
                for category in UpworkService.CATEGORIES.keys()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    projects.extend(result)
                elif isinstance(result, Exception):
                    logger.error("fetch_error", error=str(result))
            
            unique_projects = {p["external_id"]: p for p in projects}.values()
            
            async with async_session() as db:
                for project_data in unique_projects:
                    existing = await db.execute(
                        select(Project).where(Project.external_id == project_data["external_id"])
                    )
                    if existing.scalar_one_or_none():
                        continue
                    
                    project = Project(
                        external_id=project_data["external_id"],
                        title=project_data["title"],
                        description=project_data["description"],
                        budget_min=project_data.get("budget_min"),
                        budget_max=project_data.get("budget_max"),
                        budget_type=project_data.get("budget_type"),
                        deadline=project_data.get("deadline"),
                        category=project_data.get("category"),
                        skills=format_list_field(project_data.get("skills", [])),
                        url=project_data["url"],
                        posted_at=project_data.get("posted_at"),
                        created_at=datetime.utcnow()
                    )
                    db.add(project)
                
                await db.commit()
            
            await CacheService.update_cache(redis_client)
            await redis_client.close()
            
            logger.info("projects_fetched", count=len(unique_projects))
            
        except Exception as e:
            logger.error("fetch_error", error=str(e))
            await redis_client.close()
    
    @staticmethod
    async def _fetch_category_jobs(category: str, redis_client) -> List[Dict]:
        projects = []
        
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            try:
                url = f"{UpworkService.API_URL}/jobs"
                params = {
                    "q": "",
                    "sort": "recency",
                    "userJobSearchHistory": "[]",
                    "savedSearchKey": "",
                    "savedSearchId": "0",
                    "paging": json.dumps({"offset": 0, "count": 50}),
                    "jobType": "fixed",
                    "category2": json.dumps([{"uid": category}])
                }
                
                headers = UpworkService.HEADERS.copy()
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        jobs = data.get("jobs", [])
                        
                        for job in jobs:
                            project = UpworkService._parse_job(job, category)
                            if project:
                                projects.append(project)
                    else:
                        logger.warning("category_fetch_failed", category=category, status=response.status)
                        
            except Exception as e:
                logger.error("category_error", category=category, error=str(e))
        
        return projects
    
    @staticmethod
    def _parse_job(job: Dict, category: str) -> Optional[Dict]:
        try:
            job_id = job.get("uid") or job.get("id") or job.get("jobId")
            if not job_id:
                return None
            
            title = job.get("title", "")
            description = job.get("description") or job.get("snippet", "")
            
            budget_data = job.get("amount", {})
            if isinstance(budget_data, dict):
                budget_min = budget_data.get("minAmount")
                budget_max = budget_data.get("maxAmount")
                budget_type = budget_data.get("type", "fixed")
            else:
                budget_min = budget_data if budget_data else None
                budget_max = None
                budget_type = "fixed"
            
            skills = []
            if "skills" in job:
                skills = [s.get("name", s) if isinstance(s, dict) else s for s in job.get("skills", [])]
            elif "attrs" in job:
                skills = [a.get("value", "") for a in job.get("attrs", []) if a.get("name") == "skill"]
            
            posted_at = None
            if job.get("postedOn"):
                try:
                    posted_at = datetime.fromisoformat(job["postedOn"].replace("Z", "+00:00"))
                except:
                    pass
            
            return {
                "external_id": str(job_id),
                "title": title,
                "description": description,
                "budget_min": float(budget_min) if budget_min else None,
                "budget_max": float(budget_max) if budget_max else None,
                "budget_type": budget_type,
                "category": UpworkService.CATEGORIES.get(category, category),
                "skills": skills,
                "url": f"{UpworkService.BASE_URL}/jobs/{job_id}",
                "posted_at": posted_at
            }
            
        except Exception as e:
            logger.error("parse_error", error=str(e))
            return None
    
    @staticmethod
    async def fetch_user_specific_projects(user_id: int, filters: Dict) -> List[Dict]:
        async with async_session() as db:
            result = await db.execute(
                select(UserSession).where(UserSession.user_id == user_id)
            )
            user_session = result.scalar_one_or_none()
            
            if not user_session or not user_session.access_token:
                return []
            
            headers = UpworkService.HEADERS.copy()
            headers["Authorization"] = f"Bearer {user_session.access_token}"
            
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=30)
            
            projects = []
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                if user_session.proxy_url:
                    pass
                
                url = f"{UpworkService.API_URL}/jobs"
                params = {
                    "q": " ".join(filters.get("keywords_include", [])),
                    "sort": "recency",
                    "paging": json.dumps({"offset": 0, "count": 50}),
                }
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        jobs = data.get("jobs", [])
                        
                        for job in jobs:
                            project = UpworkService._parse_job(job, "custom")
                            if project:
                                projects.append(project)
            
            return projects
    
    @staticmethod
    async def refresh_user_session(user_id: int) -> bool:
        async with async_session() as db:
            result = await db.execute(
                select(UserSession).where(UserSession.user_id == user_id)
            )
            user_session = result.scalar_one_or_none()
            
            if not user_session or not user_session.refresh_token:
                return False
            
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                url = f"{UpworkService.BASE_URL}/api/v3/oauth2/token"
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": user_session.refresh_token,
                    "client_id": settings.UPWORK_CLIENT_ID,
                    "client_secret": settings.UPWORK_CLIENT_SECRET
                }
                
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        user_session.access_token = token_data.get("access_token")
                        user_session.refresh_token = token_data.get("refresh_token")
                        await db.commit()
                        return True
            
            return False
