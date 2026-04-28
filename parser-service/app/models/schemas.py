from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ProjectModel(BaseModel):
    id: str
    title: str
    description: str
    budget: Optional[float]
    deadline: Optional[datetime]
    category: str
    skills: List[str]
    created_at: datetime

class FilterModel(BaseModel):
    categories: Optional[List[str]] = None
    keywords_include: Optional[List[str]] = None
    keywords_exclude: Optional[List[str]] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
