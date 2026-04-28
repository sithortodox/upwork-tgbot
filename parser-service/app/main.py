import sys
sys.path.insert(0, '/app')

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.services.upwork import UpworkService
from app.services.cache import CacheService
from shared.database import init_db
import structlog
import asyncio
from datetime import datetime

logger = structlog.get_logger()

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.add_job(
        UpworkService.fetch_and_store_projects,
        IntervalTrigger(minutes=5),
        id="fetch_projects",
        replace_existing=True
    )
    scheduler.start()
    asyncio.create_task(UpworkService.fetch_and_store_projects())
    yield
    scheduler.shutdown()

app = FastAPI(title="Parser Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/projects")
async def get_projects(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    categories: str = Query(None),
    keywords_include: str = Query(None),
    keywords_exclude: str = Query(None),
    budget_min: float = Query(None),
    budget_max: float = Query(None)
):
    return await CacheService.get_projects(
        limit=limit,
        offset=offset,
        categories=categories,
        keywords_include=keywords_include,
        keywords_exclude=keywords_exclude,
        budget_min=budget_min,
        budget_max=budget_max
    )

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    return await CacheService.get_project_by_id(project_id)

@app.post("/refresh")
async def refresh_projects():
    await UpworkService.fetch_and_store_projects()
    return {"status": "success"}

@app.get("/categories")
async def get_categories():
    return await CacheService.get_categories()

@app.post("/auth/login/{user_id}")
async def login_upwork(user_id: int):
    from app.services.upwork_login import upwork_login_service
    from shared.database import async_session
    from shared.models_db import User, UserSession
    from sqlalchemy import select
    from shared.crypto import crypto_service
    
    async with async_session() as db:
        result = await db.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return {"status": "error", "message": "User not found"}
        
        session_result = await db.execute(
            select(UserSession).where(UserSession.user_id == user.id)
        )
        user_session = session_result.scalar_one_or_none()
        
        if not user_session:
            return {"status": "error", "message": "No session data"}
        
        if not user_session.upwork_email or not user_session.upwork_password_encrypted:
            return {"status": "error", "message": "No credentials stored"}
        
        password = crypto_service.decrypt(user_session.upwork_password_encrypted)
        totp_secret = None
        if user_session.upwork_2fa_secret:
            totp_secret = crypto_service.decrypt(user_session.upwork_2fa_secret)
        
        user_session.login_status = "in_progress"
        await db.commit()
    
    try:
        result = await upwork_login_service.login(
            email=user_session.upwork_email,
            password=password,
            totp_secret=totp_secret,
            existing_cookies=user_session.cookies,
            headless=True
        )
        
        async with async_session() as db:
            session_result = await db.execute(
                select(UserSession).where(UserSession.user_id == user.id)
            )
            user_session = session_result.scalar_one_or_none()
            
            if result["success"]:
                user_session.cookies = result["cookies"]
                user_session.cookies_updated_at = datetime.utcnow()
                user_session.login_status = "active"
                await db.commit()
                return {"status": "success", "message": "Login successful"}
            else:
                user_session.login_status = "failed"
                await db.commit()
                return {"status": "error", "message": result.get("error", "Login failed")}
    
    except Exception as e:
        async with async_session() as db:
            session_result = await db.execute(
                select(UserSession).where(UserSession.user_id == user.id)
            )
            user_session = session_result.scalar_one_or_none()
            user_session.login_status = "failed"
            await db.commit()
        
        logger.error("login_exception", error=str(e))
        return {"status": "error", "message": str(e)}
