from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    REDIS_URL: str = os.getenv("REDIS_URL")

settings = Settings()
