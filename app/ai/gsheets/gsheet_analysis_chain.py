"""gsheet_analysis_chain.py – LLM-powered analysis of Google Sheet data.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.

This chain:
1. Takes a user question + sheet_data (from gsheet_loader).
2. Applies deterministic dataframe operations (sheets_dataframe_service).
3. Builds an LLM prompt (gsheet_prompt_builder).
4. Calls the LLM via the existing LiteLLM proxy.
5. Returns a structured result compatible with SQLChatResponse.result.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.ai.gsheets.gsheet_prompt_builder import (
    build_analysis_prompt,
    build_system_message,
)
from app.core.config import get_settings
from app.services.dataframe_agent_service import DataframeAgentError, answer_question_from_rows
from app.services.sheets_dataframe_service import (
    DataframeAnalysisError,
    apply_dataframe_analysis,
)
from app.utils.response_formatter import build_query_result

logger = logging.getLogger(__name__)


async def run_gsheet_analysis(
    question: str,
    sheet_data: dict[str, Any],
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Analyse *sheet_data* using the given *question* and return a result dict.

    The result dict matches the shape returned by
    :func:`app.utils.response_formatter.build_query_result` so the frontend
    can render it the same way as SQL results.
    """
    t0 = time.perf_counter()
    preview_rows = sheet_data.get("preview_rows", [])
    sheet_name = sheet_data.get("sheet_name", "Sheet1")

    logger.info(
        "[gsheet_analysis] start question=%r sheet=%s rows=%d",
        question,
        sheet_name,
        len(preview_rows),
    )

    # Step 1: Deterministic dataframe analysis (fast, no LLM cost)
    try:
        df_result = apply_dataframe_analysis(preview_rows, question, page=page, page_size=page_size)
        rows = df_result.get("rows", [])
        total_rows = df_result.get("total_rows", 0)
        has_more = df_result.get("has_more", False)
        df_summary = df_result.get("summary", "")
        columns = df_result.get("columns", [])
    except DataframeAnalysisError as exc:
        raise ValueError(str(exc)) from exc

    # Step 2: LLM explanation / enrichment via Pandas dataframe agent
    llm_summary = df_summary
    try:
        llm_summary = await answer_question_from_rows(question, preview_rows)
    except DataframeAgentError as exc:
        logger.warning("[gsheet_analysis] dataframe agent failed (using df_summary): %s", exc)
        llm_summary = df_summary
    except Exception as exc:  # noqa: BLE001
        logger.warning("[gsheet_analysis] dataframe agent unexpected failure (using df_summary): %s", exc)

    duration = time.perf_counter() - t0
    logger.info(
        "[gsheet_analysis] complete duration=%.3f result_rows=%d",
        duration,
        len(rows),
    )

    return build_query_result(
        source_type="gsheet",
        generated_sql=None,
        sql_explanation=None,
        summary=llm_summary or df_summary,
        columns=columns,
        rows=rows,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


async def _call_llm(question: str, sheet_data: dict[str, Any]) -> str:
    """Call the LLM and return the generated summary text."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    litellm_key = settings.LITELLM_API_KEY or settings.LITELLM_VIRTUAL_KEY

    llm = ChatOpenAI(
        model=settings.LITELLM_MODEL,
        openai_api_key=litellm_key,
        openai_api_base=settings.LITELLM_PROXY_URL,
        temperature=0.2,
        max_tokens=800,
        model_kwargs={"user": settings.LITELLM_USER_ID},
    )

    system_msg = SystemMessage(content=build_system_message())
    human_msg = HumanMessage(content=build_analysis_prompt(question, sheet_data))

    response = await llm.ainvoke([system_msg, human_msg])
    content = response.content.strip() if hasattr(response, "content") else str(response)

    # Extract "SUMMARY:" line if present, otherwise use full response
    for line in content.splitlines():
        if line.startswith("SUMMARY:"):
            return line[len("SUMMARY:"):].strip()

    return content
