import sys
sys.path.insert(0, '/app')

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    UPWORK_CLIENT_ID: str = ""
    UPWORK_CLIENT_SECRET: str = ""
    DEFAULT_PROXY: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
