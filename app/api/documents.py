from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.ingestion import ingest_document_chunks, split_pages_into_chunks
from app.core.config import get_settings, get_upload_root
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services import thread_service, document_service, pdf_parser

router = APIRouter(prefix="/documents", tags=["Documents"])


def error_detail(error: str, message: str):
    return {"error": error, "message": message}


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    thread_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    print("[documents] PDF upload received:", file.filename)

    thread = await thread_service.get_thread_by_id(db, thread_id, current_user.id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("thread_not_found", "Thread not found"),
        )

    try:
        content = await file.read()
        file_size = len(content)
        mime_type = file.content_type or "application/octet-stream"
        original_filename = file.filename or "document.pdf"

        document_service.validate_pdf_upload(
            filename=original_filename,
            mime_type=mime_type,
            file_size=file_size,
            max_upload_mb=settings.MAX_UPLOAD_MB,
        )

        upload_dir = get_upload_root() / "documents"
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = document_service.build_stored_filename(original_filename)
        stored_path = upload_dir / stored_filename
        stored_path.write_bytes(content)

        document = await document_service.create_document(
            db,
            user_id=current_user.id,
            thread_id=thread_id,
            filename=stored_filename,
            original_filename=original_filename,
            file_path=str(stored_path),
            mime_type=mime_type,
            processing_status="processing",
        )
        print("[documents] PDF saved locally:", stored_path)

        pages = pdf_parser.extract_pdf_pages(str(stored_path))
        if not pages:
            raise ValueError("Unable to extract readable text from PDF")
        print("[documents] PDF text extracted page count:", len(pages))

        chunks = split_pages_into_chunks(pages)
        if not chunks:
            raise ValueError("Unable to create text chunks from PDF")
        print("[documents] chunk count:", len(chunks))

        ingest_document_chunks(
            user_id=current_user.id,
            document_id=document.id,
            thread_id=thread_id,
            filename=original_filename,
            chunks=chunks,
        )

        await document_service.update_document_status(db, document, "completed")
        await db.commit()
        await db.refresh(document)
        print("[documents] document processing completed id:", document.id)
        return document

    except HTTPException:
        await db.rollback()
        raise
    except (ValueError, RuntimeError) as exc:
        await db.rollback()
        print("[documents] validation/processing error:", str(exc))

        if 'document' in locals() and document is not None:
            try:
                await document_service.update_document_status(db, document, "failed")
                await db.commit()
            except Exception:
                await db.rollback()

        if 'stored_path' in locals() and isinstance(stored_path, Path) and stored_path.exists():
            stored_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("document_validation_failed", str(exc)),
        )
    except Exception as exc:
        await db.rollback()
        print("[documents] document processing failed:", str(exc))
        # Persist failed status if document row was created
        try:
            if 'document' in locals() and document is not None:
                await document_service.update_document_status(db, document, "failed")
                await db.commit()
        except Exception:
            await db.rollback()

        # Cleanup written file on failure
        if 'stored_path' in locals() and isinstance(stored_path, Path) and stored_path.exists():
            stored_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("document_processing_failed", "Unable to process PDF"),
        )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    thread_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if thread_id:
        thread = await thread_service.get_thread_by_id(db, thread_id, current_user.id)
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_detail("thread_not_found", "Thread not found"),
            )

    docs = await document_service.get_documents_for_user(db, current_user.id, thread_id)
    return docs
