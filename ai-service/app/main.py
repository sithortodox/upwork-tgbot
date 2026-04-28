import sys
sys.path.insert(0, '/app')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
from app.services.openai_service import OpenAIService
from shared.database import init_db
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="AI Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    user_id: int
    project_title: str
    project_description: str
    additional_context: Optional[str] = None
    system_prompt: Optional[str] = None
    style_example: Optional[str] = None

class PromptUpdate(BaseModel):
    user_id: int
    prompt: str

class StyleImport(BaseModel):
    user_id: int
    text: str

class GenerateResponse(BaseModel):
    cover_letter: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/generate", response_model=GenerateResponse)
async def generate_cover_letter(request: GenerateRequest):
    cover_letter = await OpenAIService.generate(
        user_id=request.user_id,
        project_title=request.project_title,
        project_description=request.project_description,
        additional_context=request.additional_context,
        system_prompt=request.system_prompt,
        style_example=request.style_example
    )
    return GenerateResponse(cover_letter=cover_letter)

@app.get("/prompt/{user_id}")
async def get_prompt(user_id: int):
    return await OpenAIService.get_prompt(user_id)

@app.put("/prompt")
async def update_prompt(data: PromptUpdate):
    await OpenAIService.update_prompt(data.user_id, data.prompt)
    return {"status": "success"}

@app.post("/import-style")
async def import_style(data: StyleImport):
    await OpenAIService.import_style(data.user_id, data.text)
    return {"status": "success"}
