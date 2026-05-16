"""gsheet_prompt_builder.py – build LLM prompts for Google Sheet analysis.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.
"""
from __future__ import annotations

import json
from typing import Any


def build_analysis_prompt(
    question: str,
    sheet_data: dict[str, Any],
) -> str:
    """Return a system+user prompt string for the LLM to analyse *sheet_data*.

    Parameters
    ----------
    question:
        The user's natural-language question.
    sheet_data:
        Output from :func:`gsheet_loader.load_for_analysis` (contains
        ``columns``, ``preview_rows``, ``total_rows``, ``sheet_name``, etc.)
    """
    sheet_name = sheet_data.get("sheet_name", "Sheet1")
    spreadsheet_title = sheet_data.get("spreadsheet_title", "Google Sheet")
    columns = sheet_data.get("columns", [])
    preview_rows = sheet_data.get("preview_rows", [])
    total_rows = sheet_data.get("total_rows", 0)

    sample_rows = preview_rows[:15]
    sample_json = json.dumps(sample_rows, ensure_ascii=False, indent=2)

    # Clip sample to prevent token overflow (≈8 000 chars)
    if len(sample_json) > 8_000:
        sample_rows = preview_rows[:5]
        sample_json = json.dumps(sample_rows, ensure_ascii=False, indent=2)

    columns_str = ", ".join(columns)

    prompt = f"""You are an expert data analyst.

You have been given access to a Google Sheet named "{spreadsheet_title}" (tab: "{sheet_name}").

SHEET METADATA:
- Total rows: {total_rows}
- Columns ({len(columns)}): {columns_str}

SAMPLE DATA (first {len(sample_rows)} rows):
{sample_json}

USER QUESTION:
{question}

INSTRUCTIONS:
1. Answer the user's question based on the data provided.
2. If the sample is representative, give a direct answer.
3. If the question requires aggregate calculations (sum, average, count, etc.) that need all rows, state that you are working with the sample and caveat accordingly.
4. Format numbers nicely (e.g., 1,234.56).
5. Keep the answer concise, clear, and business-friendly.
6. If the data is insufficient to answer, say so honestly.
7. End with a short one-sentence summary prefixed with "SUMMARY:" on its own line.
"""
    return prompt


def build_system_message() -> str:
    """Return a system message for the Google Sheet analysis assistant."""
    return (
        "You are a helpful AI data analyst assistant specialised in analysing "
        "Google Sheets data. You provide clear, accurate, and actionable insights "
        "from spreadsheet data. Always be concise and business-friendly."
    )
