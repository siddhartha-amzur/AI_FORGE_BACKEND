from __future__ import annotations

from pydantic import BaseModel


class UploadPreviewResponse(BaseModel):
    source_id: str
    source_type: str
    display_name: str
    total_rows: int
    columns: list[str]
    preview_rows: list[dict]
    sheet_names: list[str] = []
    selected_sheet: str | None = None
    column_types: dict[str, str] = {}
