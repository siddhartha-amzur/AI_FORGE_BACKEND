from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database Configuration
    DATABASE_URL: str
    
    # JWT Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # LiteLLM Configuration
    LITELLM_PROXY_URL: str = "http://litellm.amzur.com:4000"
    LITELLM_VIRTUAL_KEY: str
    LITELLM_USER_ID: str
    LITELLM_MODEL: str = "gemini/gemini-2.5-flash"
    LITELLM_MAX_TOKENS: int = 1200
    MAX_UPLOAD_MB: int = 20
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_MIME_TYPES: str = ""
    
    # Google OAuth Configuration (optional for local/dev startup)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_upload_root() -> Path:
    """Get the absolute upload directory path."""
    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    if upload_dir.is_absolute():
        return upload_dir
    return (BASE_DIR / upload_dir).resolve()
