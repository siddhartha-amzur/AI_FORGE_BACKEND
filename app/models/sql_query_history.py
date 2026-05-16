from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base import Base


class SQLQueryHistory(Base):
    __tablename__ = "sql_query_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False, index=True)
    source_type = Column(String, nullable=False, default="postgres")
    question = Column(String, nullable=False)
    generated_sql = Column(String, nullable=False)
    sql_explanation = Column(String, nullable=False, default="")
    result_summary = Column(String, nullable=False, default="")
    filters_json = Column(String, nullable=False, default="{}")
    aggregations_json = Column(String, nullable=False, default="{}")
    result_preview_json = Column(String, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
