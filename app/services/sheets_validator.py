"""sheets_validator.py – validate and parse Google Sheets URLs.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Matches: https://docs.google.com/spreadsheets/d/<ID>/...
_SHEET_ID_RE = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)"
)
# Optional gid query param for a specific tab
_GID_RE = re.compile(r"[?&]gid=(\d+)")


class SheetURLError(ValueError):
    """Raised when the supplied URL is not a valid Google Sheets URL."""


@dataclass
class ParsedSheetURL:
    spreadsheet_id: str
    gid: str  # "0" for first sheet
    original_url: str


def validate_and_parse(url: str) -> ParsedSheetURL:
    """Validate *url* and return a :class:`ParsedSheetURL`.

    Raises :class:`SheetURLError` on any validation failure.
    """
    if not url or not url.strip():
        raise SheetURLError("Google Sheet URL must not be empty.")

    url = url.strip()

    if "docs.google.com/spreadsheets" not in url:
        raise SheetURLError(
            "Invalid URL: must be a Google Sheets URL "
            "(https://docs.google.com/spreadsheets/d/…)."
        )

    id_match = _SHEET_ID_RE.search(url)
    if not id_match:
        raise SheetURLError(
            "Could not extract spreadsheet ID from the URL. "
            "Expected format: https://docs.google.com/spreadsheets/d/<ID>/…"
        )

    spreadsheet_id = id_match.group(1)

    gid_match = _GID_RE.search(url)
    gid = gid_match.group(1) if gid_match else "0"

    return ParsedSheetURL(
        spreadsheet_id=spreadsheet_id,
        gid=gid,
        original_url=url,
    )
