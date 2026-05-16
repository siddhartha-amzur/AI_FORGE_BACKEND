from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.data_source import DataSourceResponse, GoogleSheetConnectRequest

# NEW Project 9 schemas and services (do not replace existing imports above)
from app.schemas.gsheet import (
    GSheetAnalyzeRequest,
    GSheetAnalyzeResponse,
    GSheetConnectV2Request,
    GSheetConnectV2Response,
)
from app.services import data_source_service, datasource_context_service, gsheet_service, thread_service
from app.services.sheets_service import SheetsServiceError, load_sheet
from app.services.query_history_service import record_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gsheets", tags=["Google Sheets"])


def _looks_like_html_rows(rows: list[dict[str, object]]) -> bool:
    if not rows:
        return False
    sample = " ".join(str(v) for v in rows[0].values() if v is not None).lower()
    return (
        "<html" in sample
        or "temporary redirect" in sample
        or "gse default error" in sample
    )


@router.post("/connect", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def connect_google_sheet(
    payload: GoogleSheetConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await thread_service.get_thread_by_id(db, payload.thread_id, current_user.id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "thread_not_found", "message": "Thread not found"})

    try:
        preview = await gsheet_service.fetch_public_sheet_preview(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "gsheet_invalid", "message": str(exc)})

    source = await data_source_service.create_data_source(
        db,
        user_id=current_user.id,
        thread_id=payload.thread_id,
        source_type="gsheet",
        display_name=f"Google Sheet {preview['sheet_id']}",
        location_ref=payload.url,
        row_count=preview["total_rows"],
        meta_json=json.dumps(preview),
    )

    await datasource_context_service.set_active_context(
        db,
        user_id=current_user.id,
        thread_id=payload.thread_id,
        source_type="gsheet",
        source_ref=payload.url,
        context=preview,
    )
    await db.commit()
    await db.refresh(source)
    return source


# ---------------------------------------------------------------------------
# Project 9 – NEW endpoints (service-account auth + AI analysis)
# ---------------------------------------------------------------------------

@router.post(
    "/connect/v2",
    response_model=GSheetConnectV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Connect Google Sheet (service-account auth with gspread fallback)",
)
async def connect_google_sheet_v2(
    payload: GSheetConnectV2Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Google Sheet using the service-account credentials (if configured).

    Falls back to public CSV export when ``GOOGLE_SERVICE_ACCOUNT_JSON`` is
    not set so the endpoint works in dev without any credentials.
    """
    logger.info(
        "[gsheets.connect_v2] user=%s thread=%s url=%s",
        current_user.id,
        payload.thread_id,
        payload.url,
    )

    thread = await thread_service.get_thread_by_id(db, payload.thread_id, current_user.id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "thread_not_found", "message": "Thread not found"},
        )

    try:
        sheet_data = await load_sheet(payload.url)
    except SheetsServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "gsheet_connect_failed", "message": str(exc)},
        )

    sheet_name = sheet_data.get("sheet_name", "Sheet1")
    spreadsheet_title = sheet_data.get("spreadsheet_title", f"Sheet {sheet_data.get('sheet_id', '')[:8]}")
    columns = sheet_data.get("columns", [])
    preview_rows = sheet_data.get("preview_rows", [])
    total_rows = sheet_data.get("total_rows", 0)
    gid = sheet_data.get("gid", "0")

    display_name = f"{spreadsheet_title} – {sheet_name}" if sheet_name != "Sheet1" else spreadsheet_title
    meta = {
        "sheet_name": sheet_name,
        "spreadsheet_title": spreadsheet_title,
        "columns": columns,
        "preview_rows": preview_rows,
        "total_rows": total_rows,
        "sheet_url": payload.url,
        "sheet_id": sheet_data.get("sheet_id", ""),
        "gid": gid,
    }

    logger.info("[gsheets.connect_v2] auth_success rows=%d cols=%d", total_rows, len(columns))

    source = await data_source_service.create_data_source(
        db,
        user_id=current_user.id,
        thread_id=payload.thread_id,
        source_type="gsheet",
        display_name=display_name,
        location_ref=payload.url,
        row_count=total_rows,
        meta_json=json.dumps(meta),
    )

    await datasource_context_service.set_active_context(
        db,
        user_id=current_user.id,
        thread_id=payload.thread_id,
        source_type="gsheet",
        source_ref=payload.url,
        context=meta,
    )
    await db.commit()
    await db.refresh(source)

    logger.info("[gsheets.connect_v2] datasource created id=%s", source.id)

    return GSheetConnectV2Response(
        source_id=str(source.id),
        sheet_name=sheet_name,
        spreadsheet_title=spreadsheet_title,
        columns=columns,
        preview_rows=preview_rows[:20],
        total_rows=total_rows,
        sheet_url=payload.url,
        sheet_id=sheet_data.get("sheet_id", ""),
        gid=gid,
    )


@router.post(
    "/analyze",
    response_model=GSheetAnalyzeResponse,
    summary="Analyse an active Google Sheet with a natural-language question",
)
async def analyze_google_sheet(
    payload: GSheetAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run AI-powered analysis on the active Google Sheet for the given thread."""
    from app.ai.gsheets.gsheet_analysis_chain import run_gsheet_analysis
    from app.services.sheets_validator import validate_and_parse

    logger.info(
        "[gsheets.analyze] user=%s thread=%s question=%r",
        current_user.id,
        payload.thread_id,
        payload.question,
    )

    thread = await thread_service.get_thread_by_id(db, payload.thread_id, current_user.id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "thread_not_found", "message": "Thread not found"},
        )

    active = await datasource_context_service.get_active_context(
        db, user_id=current_user.id, thread_id=payload.thread_id
    )
    if not active or active.source_type != "gsheet":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_gsheet_context",
                "message": "No active Google Sheet connected to this thread. Connect a sheet first.",
            },
        )

    sheet_url = active.source_ref
    context_obj = json.loads(active.context_json or "{}")
    preview_rows = context_obj.get("preview_rows", [])

    # Re-fetch if preview is stale/empty or if it looks like HTML redirect payload.
    if (not preview_rows) or _looks_like_html_rows(preview_rows):
        try:
            fresh = await load_sheet(sheet_url)
            preview_rows = fresh.get("preview_rows", [])
            context_obj.update(fresh)

            await datasource_context_service.set_active_context(
                db,
                user_id=current_user.id,
                thread_id=payload.thread_id,
                source_type="gsheet",
                source_ref=sheet_url,
                context=context_obj,
            )
        except SheetsServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "gsheet_reload_failed", "message": str(exc)},
            )

    if not preview_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "gsheet_empty", "message": "The connected Google Sheet has no data rows."},
        )

    sheet_data = {**context_obj, "preview_rows": preview_rows}

    logger.info("[gsheets.analyze] analysis_started rows=%d", len(preview_rows))

    try:
        result = await run_gsheet_analysis(
            question=payload.question,
            sheet_data=sheet_data,
            page=payload.page,
            page_size=payload.page_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "analysis_failed", "message": str(exc)},
        )
    except Exception as exc:
        logger.exception("[gsheets.analyze] unexpected error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "analysis_error", "message": str(exc)},
        )

    # Record in query history (reuse existing service)
    try:
        await record_query(
            db,
            user_id=current_user.id,
            thread_id=payload.thread_id,
            source_type="gsheet",
            question=payload.question,
            sql="N/A (gsheet analysis)",
            sql_explanation="Google Sheets AI analysis",
            summary=result.get("summary", ""),
            filters={},
            aggregations={},
            result_preview=result.get("rows", [])[:10],
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[gsheets.analyze] failed to record query history: %s", exc)
        await db.rollback()

    return GSheetAnalyzeResponse(
        thread_id=str(payload.thread_id),
        result=result,
    )
