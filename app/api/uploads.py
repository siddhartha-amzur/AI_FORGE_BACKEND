from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services import attachment_service, thread_service, upload_service


router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    thread_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        print("[uploads] file received:", file.filename)
        print("[uploads] mime type:", file.content_type)
        print("[uploads] thread_id:", thread_id)
        print("[uploads] user_id:", current_user.id)

        thread = await thread_service.get_thread_by_id(db, thread_id, current_user.id)
        if not thread:
            print("[uploads] ERROR: thread not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "thread_not_found", "message": "Thread not found"},
            )

        attachment = await upload_service.save_upload(
            db,
            file=file,
            user_id=current_user.id,
            thread_id=thread_id,
        )
        print("[uploads] attachment saved id:", attachment.id)
        print("[uploads] attachment stored path:", attachment.file_path)
        return attachment
    except HTTPException as exc:
        print(f"[uploads] HTTP error {exc.status_code}: {exc.detail}")
        raise
    except Exception as exc:
        print(f"[uploads] UNEXPECTED ERROR: {type(exc).__name__}: {str(exc)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "upload_failed", "message": str(exc)},
        )


@router.get("/{attachment_id}")
async def get_attachment_file(
    attachment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attachment = await attachment_service.get_attachment_by_id(db, attachment_id, current_user.id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "attachment_not_found", "message": "Attachment not found"},
        )

    print("[uploads] serving attachment id:", attachment.id)
    print("[uploads] serving path:", attachment.file_path)

    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "attachment_missing", "message": "Stored file is missing"},
        )

    return FileResponse(
        path=file_path,
        media_type=attachment.mime_type,
        filename=attachment.original_filename,
    )