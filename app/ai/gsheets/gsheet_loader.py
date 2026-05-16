"""gsheet_loader.py – load a Google Sheet into a structured analysis payload.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.sheets_service import SheetsServiceError, load_sheet

logger = logging.getLogger(__name__)


class SheetLoadError(RuntimeError):
    """Raised when the sheet cannot be loaded for analysis."""


async def load_for_analysis(
    url: str,
    sa_json: str | None = None,
) -> dict[str, Any]:
    """Load a Google Sheet and return a payload ready for the analysis chain.

    Parameters
    ----------
    url:
        Full Google Sheets URL.
    sa_json:
        Optional service-account JSON string (overrides env setting).

    Returns
    -------
    dict with: sheet_name, spreadsheet_title, columns, preview_rows,
    total_rows, sheet_id, gid, sheet_url.
    """
    logger.info("[gsheet_loader] load_for_analysis url=%s", url)

    try:
        data = await load_sheet(url, sa_json=sa_json)
    except SheetsServiceError as exc:
        logger.error("[gsheet_loader] load failed: %s", exc)
        raise SheetLoadError(str(exc)) from exc

    if not data.get("preview_rows"):
        raise SheetLoadError("The Google Sheet loaded successfully but contains no rows.")

    logger.info(
        "[gsheet_loader] loaded sheet=%s rows=%d cols=%d",
        data.get("sheet_name"),
        data.get("total_rows", 0),
        len(data.get("columns", [])),
    )
    return data
