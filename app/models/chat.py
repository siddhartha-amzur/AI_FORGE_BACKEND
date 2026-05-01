from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.db.base import Base


class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    message = Column(String, nullable=False)
    response = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
