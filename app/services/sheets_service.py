"""sheets_service.py – load Google Sheets using service-account credentials.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.

Usage priority:
1. If GOOGLE_SERVICE_ACCOUNT_JSON env var is set → use gspread (supports
   private sheets shared with the service-account email).
2. Otherwise → fall back to the public CSV-export approach so the app still
   works in dev without credentials.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.services.sheets_validator import SheetURLError, validate_and_parse

logger = logging.getLogger(__name__)

# In-process LRU-style cache: key → (timestamp, data)
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 120  # 2 minutes

_MAX_PREVIEW_ROWS = 100  # rows stored for later dataframe analysis
_MAX_FULL_ROWS = 2000    # safety cap for full loads


class SheetsServiceError(RuntimeError):
    """Raised when the Google Sheets service encounters a non-recoverable error."""


def _cache_key(spreadsheet_id: str, gid: str) -> str:
    return f"{spreadsheet_id}:{gid}"


def _get_cached(key: str) -> dict[str, Any] | None:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        del _CACHE[key]
        return None
    return data


def _put_cache(key: str, data: dict[str, Any]) -> None:
    _CACHE[key] = (time.monotonic(), data)


def _build_csv_export_url(spreadsheet_id: str, gid: str = "0") -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )


def _build_gviz_csv_url(spreadsheet_id: str, gid: str = "0") -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/gviz/tq?tqx=out:csv&gid={gid}"
    )


def _looks_like_html_payload(content: bytes) -> bool:
    probe = content[:1200].decode("utf-8", errors="ignore").strip().lower()
    return (
        probe.startswith("<!doctype html")
        or probe.startswith("<html")
        or "<title>temporary redirect</title>" in probe
        or "gse default error" in probe
    )


async def _load_via_csv_export(spreadsheet_id: str, gid: str) -> dict[str, Any]:
    """Fallback: load public sheet using the CSV-export URL."""
    import httpx

    from app.services.csv_service import CSVProcessingError, parse_csv_bytes

    export_urls = [
        _build_csv_export_url(spreadsheet_id, gid),
        _build_gviz_csv_url(spreadsheet_id, gid),
    ]
    last_error: SheetsServiceError | None = None

    for export_url in export_urls:
        logger.info("[sheets_service] csv_export url=%s", export_url)

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(
                export_url,
                headers={
                    "Accept": "text/csv,application/csv,text/plain;q=0.9,*/*;q=0.8",
                    "User-Agent": "ai-forge-sheets/1.0",
                },
            )

        if response.status_code == 403:
            raise SheetsServiceError(
                "Google Sheet is private or access denied. "
                "Share the sheet publicly (Anyone with the link) or with the service account."
            )
        if response.status_code >= 400:
            last_error = SheetsServiceError(
                f"Unable to fetch Google Sheet (HTTP {response.status_code})."
            )
            continue

        if _looks_like_html_payload(response.content):
            last_error = SheetsServiceError(
                "Google returned HTML instead of CSV (temporary redirect or access page). "
                "Use service-account access or ensure the sheet is public."
            )
            continue

        try:
            parsed = parse_csv_bytes(response.content)
            return parsed
        except CSVProcessingError as exc:
            last_error = SheetsServiceError(str(exc))
            continue

    raise last_error or SheetsServiceError("Unable to load Google Sheet via CSV export.")


def _load_via_gspread(spreadsheet_id: str, gid: str, sa_json: str) -> dict[str, Any]:
    """Load sheet using gspread + service account credentials (sync)."""
    try:
        import gspread  # type: ignore
    except ImportError as exc:
        raise SheetsServiceError(
            "gspread is not installed. Run: pip install gspread>=6.0"
        ) from exc

    logger.info(
        "[sheets_service] gspread auth for spreadsheet_id=%s gid=%s", spreadsheet_id, gid
    )

    try:
        sa_dict = json.loads(sa_json)
    except json.JSONDecodeError as exc:
        raise SheetsServiceError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
        ) from exc

    try:
        gc = gspread.service_account_from_dict(sa_dict)
        spreadsheet = gc.open_by_key(spreadsheet_id)
    except gspread.exceptions.APIError as exc:
        raise SheetsServiceError(f"Google API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise SheetsServiceError(f"Failed to open spreadsheet: {exc}") from exc

    # Find the worksheet by gid or default to first
    try:
        worksheet = next(
            (ws for ws in spreadsheet.worksheets() if str(ws.id) == gid),
            spreadsheet.sheet1,
        )
    except Exception as exc:  # noqa: BLE001
        raise SheetsServiceError(f"Could not load worksheet: {exc}") from exc

    logger.info("[sheets_service] gspread worksheet title=%s", worksheet.title)

    try:
        all_records = worksheet.get_all_records(
            default_blank="",
            numericise_ignore=["all"],  # keep as strings for safety
        )
    except Exception as exc:  # noqa: BLE001
        raise SheetsServiceError(f"Failed to read worksheet data: {exc}") from exc

    if not all_records:
        raise SheetsServiceError("Google Sheet appears to be empty.")

    columns = list(all_records[0].keys()) if all_records else []
    total_rows = len(all_records)
    preview_rows = all_records[:_MAX_PREVIEW_ROWS]

    logger.info(
        "[sheets_service] gspread loaded total_rows=%d columns=%s",
        total_rows,
        columns,
    )

    return {
        "sheet_name": worksheet.title,
        "spreadsheet_title": spreadsheet.title,
        "columns": columns,
        "preview_rows": preview_rows,
        "total_rows": total_rows,
        "sheet_id": spreadsheet_id,
        "gid": gid,
    }


async def load_sheet(url: str, sa_json: str | None = None) -> dict[str, Any]:
    """Main entry-point: load a Google Sheet and return a preview dict.

    Parameters
    ----------
    url:
        Full Google Sheets URL.
    sa_json:
        Optional service-account JSON string.  When *None* the function
        reads ``GOOGLE_SERVICE_ACCOUNT_JSON`` from settings; if still absent
        it falls back to the public CSV-export approach.

    Returns
    -------
    dict with keys: sheet_name, spreadsheet_title, columns, preview_rows,
    total_rows, sheet_id, gid, sheet_url.
    """
    t0 = time.perf_counter()

    try:
        parsed = validate_and_parse(url)
    except SheetURLError as exc:
        raise SheetsServiceError(str(exc)) from exc

    cache_key = _cache_key(parsed.spreadsheet_id, parsed.gid)
    cached = _get_cached(cache_key)
    if cached:
        logger.info("[sheets_service] cache_hit key=%s", cache_key)
        return cached

    # Resolve service account JSON
    if sa_json is None:
        try:
            from app.core.config import get_settings
            sa_json = get_settings().GOOGLE_SERVICE_ACCOUNT_JSON or None
        except Exception:  # noqa: BLE001
            sa_json = None

    if sa_json:
        import asyncio

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, _load_via_gspread, parsed.spreadsheet_id, parsed.gid, sa_json
        )
    else:
        logger.warning(
            "[sheets_service] GOOGLE_SERVICE_ACCOUNT_JSON not configured; "
            "falling back to CSV export (public sheets only)."
        )
        data = await _load_via_csv_export(parsed.spreadsheet_id, parsed.gid)
        # Normalise field names from csv_service output
        if "total_rows" not in data:
            data["total_rows"] = len(data.get("preview_rows", []))
        if "sheet_name" not in data:
            data["sheet_name"] = "Sheet1"
        if "spreadsheet_title" not in data:
            data["spreadsheet_title"] = f"Sheet {parsed.spreadsheet_id[:8]}"

    data["sheet_url"] = url
    data["sheet_id"] = parsed.spreadsheet_id

    _put_cache(cache_key, data)

    duration = time.perf_counter() - t0
    logger.info(
        "[sheets_service] load_complete rows=%d duration_seconds=%.3f",
        data.get("total_rows", 0),
        duration,
    )
    return data


def invalidate_cache(spreadsheet_id: str, gid: str = "0") -> None:
    """Remove a cached entry (e.g. after a reconnect)."""
    _CACHE.pop(_cache_key(spreadsheet_id, gid), None)
