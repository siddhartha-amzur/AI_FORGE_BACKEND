# Database init file to create tables
from app.db.base import Base
from app.models.user import User
from app.models.chat import Chat

# Import all models here so Alembic can see them
__all__ = ["Base", "User", "Chat"]
