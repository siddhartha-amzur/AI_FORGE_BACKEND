from __future__ import annotations

import re
from typing import Any

import httpx

from app.services.csv_service import CSVProcessingError, parse_csv_bytes
from app.utils.execution_timer import timed_block


GSHEET_RE = re.compile(r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)")


class GoogleSheetError(ValueError):
    pass


def _extract_sheet_id(url: str) -> str:
    match = GSHEET_RE.search(url)
    if not match:
        raise GoogleSheetError("Invalid Google Sheet URL")
    return match.group(1)


def _build_csv_export_url(sheet_id: str, gid: str = "0") -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


async def fetch_public_sheet_preview(url: str) -> dict[str, Any]:
    sheet_id = _extract_sheet_id(url)
    export_url = _build_csv_export_url(sheet_id)

    with timed_block("gsheet_fetch"):
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                export_url,
                headers={
                    "Accept": "text/csv,application/csv,text/plain;q=0.9,*/*;q=0.8",
                    "User-Agent": "ai-forge-sheets/1.0",
                },
            )

    if response.status_code == 403:
        raise GoogleSheetError("Google Sheet is private or access denied")
    if response.status_code >= 400:
        raise GoogleSheetError("Unable to fetch Google Sheet")

    probe = response.content[:1200].decode("utf-8", errors="ignore").strip().lower()
    if (
        probe.startswith("<!doctype html")
        or probe.startswith("<html")
        or "temporary redirect" in probe
    ):
        raise GoogleSheetError(
            "Google returned HTML instead of CSV. Share the sheet publicly or connect with service-account auth."
        )

    try:
        parsed = parse_csv_bytes(response.content)
    except CSVProcessingError as exc:
        raise GoogleSheetError(str(exc))

    if parsed["total_rows"] == 0:
        raise GoogleSheetError("Google Sheet appears empty")

    parsed["sheet_url"] = url
    parsed["sheet_id"] = sheet_id
    return parsed
