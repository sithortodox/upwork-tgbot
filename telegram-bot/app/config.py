import sys
sys.path.insert(0, '/app')

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    BOT_TOKEN: str
    API_GATEWAY_URL: str = "http://api-gateway:8000"
    REDIS_URL: str = "redis://redis:6379/0"
    DATABASE_URL: str
    UPWORK_CLIENT_ID: str = ""
    FREE_DAILY_AI_LIMIT: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
