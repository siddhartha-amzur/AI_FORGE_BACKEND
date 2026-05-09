import re
import uuid
from pathlib import Path
from typing import Set

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, get_upload_root
from app.models.attachment import Attachment
from app.services import attachment_service


ALLOWED_MIME_BY_EXTENSION = {
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".mp4": {"video/mp4"},
    ".mov": {"video/quicktime", "video/mov"},
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".py": {"text/x-python", "text/plain", "application/octet-stream"},
    ".js": {"text/javascript", "application/javascript", "text/plain", "application/octet-stream"},
    ".ts": {"video/mp2t", "application/typescript", "text/plain", "application/octet-stream"},
    ".json": {"application/json", "text/plain", "application/octet-stream"},
    ".html": {"text/html", "application/octet-stream"},
    ".css": {"text/css", "application/octet-stream"},
    ".csv": {"text/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}

DIRECTORY_BY_EXTENSION = {
    ".png": "images",
    ".jpg": "images",
    ".jpeg": "images",
    ".webp": "images",
    ".mp4": "videos",
    ".mov": "videos",
    ".pdf": "documents",
    ".txt": "documents",
    ".csv": "documents",
    ".xlsx": "documents",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".json": "code",
    ".html": "code",
    ".css": "code",
}

CHUNK_SIZE = 1024 * 1024


def _get_allowed_mime_override() -> Set[str]:
    configured = get_settings().ALLOWED_MIME_TYPES.strip()
    if not configured:
        return set()
    return {item.strip() for item in configured.split(",") if item.strip()}


def sanitize_filename(filename: str) -> str:
    safe_name = Path(filename).name
    safe_name = safe_name.replace("..", "")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
    return safe_name or "file"


def validate_upload_type(filename: str, mime_type: str) -> str:
    extension = Path(filename).suffix.lower()
    allowed_mimes = ALLOWED_MIME_BY_EXTENSION.get(extension)
    allowed_override = _get_allowed_mime_override()
    if allowed_override:
        allowed_mimes = allowed_mimes.intersection(allowed_override) if allowed_mimes else set()

    if not allowed_mimes or mime_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_file_type",
                "message": "This file type is not allowed",
            },
        )
    return extension


def ensure_upload_directories() -> None:
    upload_root = get_upload_root()
    for folder in {"images", "videos", "documents", "code"}:
        (upload_root / folder).mkdir(parents=True, exist_ok=True)


async def save_upload(
    db: AsyncSession,
    *,
    file: UploadFile,
    user_id,
    thread_id,
) -> Attachment:
    settings = get_settings()
    ensure_upload_directories()
    print("[upload_service] upload root:", get_upload_root())

    original_filename = sanitize_filename(file.filename or "file")
    mime_type = file.content_type or "application/octet-stream"
    extension = validate_upload_type(original_filename, mime_type)
    print("[upload_service] sanitized filename:", original_filename)
    print("[upload_service] detected extension:", extension)
    print("[upload_service] mime type accepted:", mime_type)

    subfolder = DIRECTORY_BY_EXTENSION[extension]
    stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = get_upload_root() / subfolder / stored_filename
    print("[upload_service] final file path:", file_path)
    print("[upload_service] file path exists before write:", file_path.exists())
    print("[upload_service] parent dir exists:", file_path.parent.exists())

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    total_size = 0

    try:
        print("[upload_service] opening file for write:", str(file_path))
        with file_path.open("wb") as destination:
            print("[upload_service] file opened successfully, writing chunks...")
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                print(f"[upload_service] wrote chunk, total bytes so far: {total_size}")
                if total_size > max_bytes:
                    print(f"[upload_service] file exceeds max size: {total_size} > {max_bytes}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "file_too_large",
                            "message": f"Maximum allowed file size is {settings.MAX_UPLOAD_MB} MB",
                        },
                    )
                destination.write(chunk)

        print("[upload_service] file written successfully, bytes:", total_size)
        print("[upload_service] file now exists on disk:", file_path.exists())

        attachment = await attachment_service.create_attachment(
            db,
            user_id=user_id,
            thread_id=thread_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            file_size=total_size,
            file_path=str(file_path),
        )
        print("[upload_service] db save success attachment_id:", attachment.id)
        return attachment
    except HTTPException:
        if file_path.exists():
            print("[upload_service] removing orphaned file:", file_path)
            file_path.unlink()
        raise
    except Exception as exc:
        print(f"[upload_service] ERROR during file write: {type(exc).__name__}: {str(exc)}")
        if file_path.exists():
            print("[upload_service] removing orphaned file:", file_path)
            file_path.unlink()
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "upload_failed", "message": str(exc)},
        )
    finally:
        await file.close()