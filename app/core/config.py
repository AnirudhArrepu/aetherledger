from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    REDIS_URL: str = os.getenv("REDIS_URL")
    # admin token for simple admin endpoints (override via env in production)
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "changeme")

settings = Settings()
