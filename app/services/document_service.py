from pathlib import Path
from typing import List, Optional
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


ALLOWED_PDF_MIME_TYPES = {"application/pdf"}


def sanitize_filename(name: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in name)
    return safe or "document.pdf"


def build_stored_filename(original_filename: str) -> str:
    safe = sanitize_filename(original_filename)
    return f"{uuid.uuid4().hex}_{safe}"


async def create_document(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID | None,
    filename: str,
    original_filename: str,
    file_path: str,
    mime_type: str,
    processing_status: str,
) -> Document:
    document = Document(
        user_id=user_id,
        thread_id=thread_id,
        filename=filename,
        original_filename=original_filename,
        file_path=file_path,
        mime_type=mime_type,
        processing_status=processing_status,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    return document


async def update_document_status(db: AsyncSession, document: Document, status: str) -> None:
    document.processing_status = status
    await db.flush()


async def get_document_by_id(db: AsyncSession, document_id: UUID, user_id: UUID) -> Optional[Document]:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_documents_for_user(
    db: AsyncSession,
    user_id: UUID,
    thread_id: UUID | None = None,
) -> List[Document]:
    query = select(Document).where(Document.user_id == user_id)
    if thread_id:
        query = query.where(Document.thread_id == thread_id)
    query = query.order_by(Document.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def has_completed_documents(
    db: AsyncSession,
    user_id: UUID,
    thread_id: UUID | None,
) -> bool:
    query = select(Document).where(
        Document.user_id == user_id,
        Document.processing_status == "completed",
    )
    if thread_id:
        query = query.where(Document.thread_id == thread_id)
    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


def validate_pdf_upload(*, filename: str, mime_type: str, file_size: int, max_upload_mb: int) -> None:
    suffix = Path(filename).suffix.lower()
    max_bytes = max_upload_mb * 1024 * 1024

    if suffix != ".pdf":
        raise ValueError("Only PDF files are allowed")
    if mime_type not in ALLOWED_PDF_MIME_TYPES:
        raise ValueError("Unsupported PDF mime type")
    if file_size > max_bytes:
        raise ValueError(f"PDF exceeds maximum size of {max_upload_mb} MB")
