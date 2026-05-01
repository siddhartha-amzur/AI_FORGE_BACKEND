from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # LiteLLM Configuration
    LITELLM_PROXY_URL: str = "http://litellm.amzur.com:4000"
    LITELLM_VIRTUAL_KEY: str
    LITELLM_USER_ID: str
    LITELLM_MODEL: str = "gemini/gemini-2.5-flash"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
