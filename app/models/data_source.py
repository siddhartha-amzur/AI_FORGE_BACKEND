from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False, index=True)
    source_type = Column(String, nullable=False)  # postgres|excel|csv|gsheet
    display_name = Column(String, nullable=False)
    location_ref = Column(String, nullable=False)  # file path or sheet URL
    status = Column(String, nullable=False, default="ready")
    row_count = Column(Integer, nullable=False, default=0)
    meta_json = Column(String, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    thread = relationship("Thread")
