from pathlib import Path
from typing import List, Dict

from pypdf import PdfReader


def extract_pdf_pages(file_path: str) -> List[Dict[str, str | int]]:
    print("[pdf_parser] extracting PDF text from:", file_path)
    try:
        reader = PdfReader(file_path)
    except Exception as exc:
        raise ValueError("Unable to parse PDF file") from exc
    pages: List[Dict[str, str | int]] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": page_number, "text": text})

    print("[pdf_parser] extracted page count:", len(pages))
    return pages


def validate_pdf_has_text(file_path: str) -> None:
    pages = extract_pdf_pages(file_path)
    combined = "\n".join(str(item["text"]) for item in pages).strip()
    if not combined:
        raise ValueError("PDF has no readable text content")


def file_size_bytes(file_path: str) -> int:
    return Path(file_path).stat().st_size
