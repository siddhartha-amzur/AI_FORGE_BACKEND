from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base import Base


class ActiveDataContext(Base):
    __tablename__ = "active_data_context"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False, index=True)
    source_type = Column(String, nullable=False, default="postgres")
    source_ref = Column(String, nullable=False, default="postgres://default")
    context_json = Column(String, nullable=False, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
