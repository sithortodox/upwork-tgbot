from pydantic import BaseModel
from typing import Optional

class AIGenerateRequest(BaseModel):
    user_id: int
    project_title: str
    project_description: str
    additional_context: Optional[str] = None

class PromptModel(BaseModel):
    user_id: int
    prompt: str

class LimitsModel(BaseModel):
    user_id: int
    daily_limit: int
    used_today: int
    plan: str
