"""gsheet.py – Pydantic schemas for Google Sheets API endpoints.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator


class GSheetConnectV2Request(BaseModel):
    """Request body for the v2 connect endpoint (service-account auth)."""

    thread_id: UUID
    url: str

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        if "docs.google.com/spreadsheets" not in v:
            raise ValueError(
                "Must be a valid Google Sheets URL "
                "(https://docs.google.com/spreadsheets/d/…)."
            )
        return v


class GSheetPreviewRow(BaseModel):
    """A single row of sheet preview data (arbitrary columns)."""

    data: dict[str, object]


class GSheetConnectV2Response(BaseModel):
    """Response returned after successfully connecting a Google Sheet."""

    source_id: str
    sheet_name: str
    spreadsheet_title: str
    columns: list[str]
    preview_rows: list[dict[str, object]]
    total_rows: int
    sheet_url: str
    sheet_id: str
    gid: str


class GSheetAnalyzeRequest(BaseModel):
    """Request body for the /analyze endpoint."""

    thread_id: UUID
    question: str
    page: int = 1
    page_size: int = 50

    @field_validator("question")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be empty.")
        return v.strip()

    @field_validator("page")
    @classmethod
    def _page_ge_1(cls, v: int) -> int:
        return max(v, 1)

    @field_validator("page_size")
    @classmethod
    def _page_size_range(cls, v: int) -> int:
        return max(1, min(v, 500))


class GSheetAnalyzeResponse(BaseModel):
    """Response from the /analyze endpoint – matches SQLChatResponse shape."""

    thread_id: str
    result: dict[str, object]
