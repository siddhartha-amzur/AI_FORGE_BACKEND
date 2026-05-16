from __future__ import annotations

from pathlib import Path


MAX_ANALYST_FILE_MB = 10
ALLOWED_ANALYST_EXTENSIONS = {".csv", ".xlsx"}


class FileValidationError(ValueError):
    pass


def validate_analyst_file(filename: str, file_size: int, max_size_mb: int = MAX_ANALYST_FILE_MB) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_ANALYST_EXTENSIONS:
        raise FileValidationError("Only CSV and XLSX files are supported for analyst uploads")

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise FileValidationError(f"File exceeds {max_size_mb} MB limit")

    return suffix
