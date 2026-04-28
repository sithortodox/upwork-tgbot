from pydantic import BaseModel
from typing import Optional
from enum import Enum

class NotificationSchedule(str, Enum):
    IMMEDIATE = "immediate"
    HOURLY = "hourly"
    DAILY = "daily"

class NotificationSettings(BaseModel):
    user_id: int
    enabled: bool = True
    schedule: NotificationSchedule = NotificationSchedule.IMMEDIATE

class NotificationMessage(BaseModel):
    user_id: int
    project_id: str
    message: str
