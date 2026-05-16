from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_upload_root
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.data_source import DataSourceResponse
from app.schemas.upload_response import UploadPreviewResponse
from app.services import csv_service, data_source_service, datasource_context_service, excel_service, thread_service
from app.utils.file_validation import FileValidationError, validate_analyst_file
from app.utils.execution_timer import timed_block


router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


@router.post("/upload", response_model=UploadPreviewResponse, status_code=status.HTTP_201_CREATED)
async def upload_data_source(
    thread_id: str = Form(...),
    file: UploadFile = File(...),
    selected_sheet: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_thread", "message": "Invalid thread id"})

    thread = await thread_service.get_thread_by_id(db, thread_uuid, current_user.id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "thread_not_found", "message": "Thread not found"})

    content = await file.read()
    try:
        suffix = validate_analyst_file(file.filename or "upload", len(content))
    except FileValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_file", "message": str(exc)})

    with timed_block("upload_processing"):
        if suffix == ".csv":
            try:
                parsed = csv_service.parse_csv_bytes(content)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "csv_parse_failed", "message": str(exc)})
            source_type = "csv"
            folder = "csv"
        else:
            try:
                parsed = excel_service.parse_excel_bytes(content, selected_sheet=selected_sheet)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "excel_parse_failed", "message": str(exc)})
            source_type = "excel"
            folder = "excel"

    upload_dir = get_upload_root() / folder
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_name = file.filename or "upload"
    stored_name = f"{uuid.uuid4().hex}_{Path(original_name).name}"
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(content)

    parsed["stored_file_path"] = str(stored_path)
    source = await data_source_service.create_data_source(
        db,
        user_id=current_user.id,
        thread_id=thread_uuid,
        source_type=source_type,
        display_name=original_name,
        location_ref=str(stored_path),
        row_count=parsed["total_rows"],
        meta_json=json.dumps(parsed, default=str),
    )

    await datasource_context_service.set_active_context(
        db,
        user_id=current_user.id,
        thread_id=thread_uuid,
        source_type=source_type,
        source_ref=str(source.id),
        context=parsed,
    )
    await db.commit()

    return UploadPreviewResponse(
        source_id=str(source.id),
        source_type=source_type,
        display_name=original_name,
        total_rows=parsed["total_rows"],
        columns=parsed["columns"],
        preview_rows=parsed["preview_rows"],
        sheet_names=parsed.get("sheet_names", []),
        selected_sheet=parsed.get("selected_sheet"),
        column_types=parsed.get("column_types", {}),
    )


@router.get("", response_model=list[DataSourceResponse])
async def list_sources(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_thread", "message": "Invalid thread id"})

    items = await data_source_service.list_data_sources(db, user_id=current_user.id, thread_id=thread_uuid)
    return items


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        source_uuid = uuid.UUID(source_id)
        thread_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_id", "message": "Invalid id"})

    source = await data_source_service.get_data_source(db, source_id=source_uuid, user_id=current_user.id, thread_id=thread_uuid)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "source_not_found", "message": "Data source not found"})

    if source.source_type in {"csv", "excel"}:
        file_path = Path(source.location_ref)
        if file_path.exists():
            file_path.unlink()

    await data_source_service.delete_data_source(db, source_id=source_uuid, user_id=current_user.id, thread_id=thread_uuid)
    await db.commit()
    return None
