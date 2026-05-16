from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator


class DataframeQARequest(BaseModel):
    question: str
    google_sheet_url: str | None = None
    file_path: str | None = None

    @field_validator("question")
    @classmethod
    def _validate_question(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("question must not be empty.")
        return value

    @field_validator("google_sheet_url")
    @classmethod
    def _validate_gsheet_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if "docs.google.com/spreadsheets" not in value:
            raise ValueError("google_sheet_url must be a valid Google Sheets URL.")
        return value

    @field_validator("file_path")
    @classmethod
    def _validate_file_path(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        return value

    @model_validator(mode="after")
    def _validate_single_source(self) -> "DataframeQARequest":
        if bool(self.google_sheet_url) == bool(self.file_path):
            raise ValueError("Provide exactly one source: google_sheet_url or file_path.")
        return self


class DataframeQAResponse(BaseModel):
    source_type: str
    answer: str
    columns: list[str]
    total_rows: int
    preview_rows: list[dict[str, object]]
    metadata: dict[str, object] = {}
