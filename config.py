# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):

    SECRET_KEY: str = "PASTE_YOUR_RANDOM_SECRET_KEY_HERE"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    OTP_EXPIRE_MINUTES: int = 5


    # SQLite (پیش‌فرض، برای شروع):
    DATABASE_URL: str = "sqlite:///./social_app.db"

    # DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/social_db"


    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 2000


    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "ChangeMe_Admin@2025"  # حتماً این را تغییر دهید!


    model_config = SettingsConfigDict(env_file=None, extra="ignore")

settings = Settings()
