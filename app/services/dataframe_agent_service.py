from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings, get_upload_root
from app.services.sheets_service import SheetsServiceError, load_sheet
from app.services.sheets_validator import SheetURLError, validate_and_parse


class DataframeAgentError(ValueError):
    pass


_BLOCKED_KEYWORDS = [
    "eval(",
    "exec(",
    "__import__",
    "lambda",
    "subprocess",
    "os.system",
    "open(",
    "import ",
]

_MAX_AGENT_ROWS = 5000


def _assert_safe_question(question: str) -> None:
    lowered = question.lower()
    for kw in _BLOCKED_KEYWORDS:
        if kw in lowered:
            raise DataframeAgentError(
                "Unsafe operation detected. Only read-only dataframe analysis is allowed."
            )


def _extract_agent_output(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        # Tool-calling agents usually return output in one of these keys.
        for key in ("output", "final_answer", "answer"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(raw, default=str)
    return str(raw)


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()
    normalized.columns = [str(col).strip() if col is not None else "" for col in normalized.columns]
    normalized = normalized.loc[:, [c for c in normalized.columns if c]]
    return normalized.head(_MAX_AGENT_ROWS)


def _load_local_dataframe(file_path: str) -> tuple[pd.DataFrame, str]:
    candidate = Path(file_path).expanduser().resolve()
    upload_root = get_upload_root().resolve()

    # Restrict reads to workspace upload directory for safety.
    if upload_root not in candidate.parents and candidate != upload_root:
        raise DataframeAgentError("file_path must point to a file under the uploads directory.")

    if not candidate.exists() or not candidate.is_file():
        raise DataframeAgentError("file_path does not exist.")

    suffix = candidate.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(candidate)
        source_type = "csv"
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(candidate)
        source_type = "excel"
    else:
        raise DataframeAgentError("Only .csv, .xlsx, and .xls files are supported.")

    return _normalize_dataframe(df), source_type


async def _load_gsheet_dataframe(url: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        validate_and_parse(url)
    except SheetURLError as exc:
        raise DataframeAgentError(str(exc)) from exc

    try:
        sheet_data = await load_sheet(url)
    except SheetsServiceError as exc:
        raise DataframeAgentError(str(exc)) from exc

    rows = sheet_data.get("preview_rows", [])
    if not rows:
        raise DataframeAgentError("Google Sheet has no rows.")

    df = pd.DataFrame(rows)
    df = _normalize_dataframe(df)

    # Detect bad HTML payloads early.
    if not df.empty:
        first_row = " ".join(str(v) for v in df.iloc[0].tolist()).lower()
        if "temporary redirect" in first_row or "<html" in first_row:
            raise DataframeAgentError(
                "Google returned a redirect HTML page instead of sheet data. "
                "Share the sheet with the configured service account or make it public."
            )

    metadata = {
        "sheet_name": sheet_data.get("sheet_name", "Sheet1"),
        "spreadsheet_title": sheet_data.get("spreadsheet_title", "Google Sheet"),
        "sheet_url": url,
        "total_rows": int(sheet_data.get("total_rows", len(df))),
    }
    return df, metadata


def _run_dataframe_agent_sync(question: str, df: pd.DataFrame) -> str:
    try:
        from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
    except ImportError as exc:
        raise DataframeAgentError(
            "Missing dependency: langchain-experimental. Install it and restart backend."
        ) from exc

    from langchain_openai import ChatOpenAI

    settings = get_settings()
    api_key = settings.LITELLM_API_KEY or settings.LITELLM_VIRTUAL_KEY

    llm = ChatOpenAI(
        model=settings.LITELLM_MODEL,
        openai_api_key=api_key,
        openai_api_base=settings.LITELLM_PROXY_URL,
        temperature=0,
        max_tokens=800,
        model_kwargs={"user": settings.LITELLM_USER_ID},
    )

    prefix = (
        "You are a strict read-only dataframe analyst. "
        "Never invent columns or rows. "
        "If data is missing, say so clearly. "
        "Return a concise plain-English answer first, then key numbers."
    )

    agent = create_pandas_dataframe_agent(
        llm=llm,
        df=df,
        agent_type="tool-calling",
        verbose=False,
        allow_dangerous_code=True,
        max_iterations=8,
        include_df_in_prompt=True,
        prefix=prefix,
    )

    result = agent.invoke({"input": question})
    return _extract_agent_output(result)


async def answer_question_from_source(
    *,
    question: str,
    google_sheet_url: str | None = None,
    file_path: str | None = None,
) -> dict[str, Any]:
    _assert_safe_question(question)

    if bool(google_sheet_url) == bool(file_path):
        raise DataframeAgentError("Provide exactly one source: google_sheet_url or file_path.")

    metadata: dict[str, Any] = {}
    if google_sheet_url:
        df, metadata = await _load_gsheet_dataframe(google_sheet_url)
        source_type = "gsheet"
    else:
        assert file_path is not None
        df, source_type = _load_local_dataframe(file_path)

    if df.empty:
        raise DataframeAgentError("DataFrame is empty. Please provide a file/sheet with rows.")

    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, _run_dataframe_agent_sync, question, df)

    preview_df = df.head(50).fillna("")
    preview_rows = preview_df.to_dict(orient="records")

    return {
        "source_type": source_type,
        "answer": answer,
        "columns": [str(c) for c in df.columns.tolist()],
        "total_rows": int(len(df)),
        "preview_rows": preview_rows,
        "metadata": metadata,
    }


async def answer_question_from_rows(question: str, rows: list[dict[str, Any]]) -> str:
    _assert_safe_question(question)
    if not rows:
        raise DataframeAgentError("No rows available for analysis.")

    df = _normalize_dataframe(pd.DataFrame(rows))
    if df.empty:
        raise DataframeAgentError("No usable rows available for analysis.")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_dataframe_agent_sync, question, df)
