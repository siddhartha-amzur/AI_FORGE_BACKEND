from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False, index=True)
    message_id = Column(String, nullable=True)  # stored as string since Message.id is int
    prompt = Column(String, nullable=False)
    image_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False, default="image/png")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    thread = relationship("Thread")
    user = relationship("User")
