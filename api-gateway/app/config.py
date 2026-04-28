from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    PARSER_SERVICE_URL: str = "http://parser-service:8001"
    AI_SERVICE_URL: str = "http://ai-service:8002"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8003"
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    FREE_DAILY_AI_LIMIT: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
