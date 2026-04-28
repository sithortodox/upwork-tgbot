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
