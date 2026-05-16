from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database Configuration
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT_SECONDS: int = 30
    
    # JWT Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # LiteLLM Configuration
    LITELLM_PROXY_URL: str = "http://litellm.amzur.com:4000"
    LITELLM_VIRTUAL_KEY: str
    LITELLM_API_KEY: str = ""
    LITELLM_USER_ID: str
    LITELLM_MODEL: str = "gemini/gemini-2.5-flash"
    LITELLM_EMBEDDING_MODEL: str = "text-embedding-3-large"
    LITELLM_MAX_TOKENS: int = 1200
    MAX_UPLOAD_MB: int = 20
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_MIME_TYPES: str = ""

    # Image Generation Configuration
    IMAGE_GEN_MODEL: str = "gemini/imagen-4.0-fast-generate-001"
    GENERATED_IMAGE_DIR: str = "./uploads/generated_images"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    RAG_TOP_K: int = 5
    
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


def get_chroma_persist_dir() -> Path:
    """Get the absolute Chroma persistence directory path."""
    settings = get_settings()
    chroma_dir = Path(settings.CHROMA_PERSIST_DIR)
    if chroma_dir.is_absolute():
        return chroma_dir
    return (BASE_DIR / chroma_dir).resolve()
