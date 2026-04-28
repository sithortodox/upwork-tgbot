from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"

class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    plan: Plan = Plan.FREE
    ai_generations_today: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    external_id: str
    title: str
    description: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[datetime] = None
    category: str
    skills: List[str] = []
    url: str

class Project(ProjectBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class FilterBase(BaseModel):
    categories: Optional[List[str]] = None
    keywords_include: Optional[List[str]] = None
    keywords_exclude: Optional[List[str]] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None

class FilterCreate(FilterBase):
    pass

class Filter(FilterBase):
    id: int
    user_id: int
    
    class Config:
        from_attributes = True

class AIPromptBase(BaseModel):
    prompt: str

class AIPrompt(AIPromptBase):
    id: int
    user_id: int
    
    class Config:
        from_attributes = True
