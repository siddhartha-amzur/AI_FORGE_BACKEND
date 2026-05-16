from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.sql.prompts import SQL_RETRY_SYSTEM
from app.ai.sql.utils import parse_llm_json
from app.services.chatbot import chatbot_service


async def repair_sql_once(*, question: str, schema_context: str, prior_sql: str, db_error: str) -> tuple[str, str]:
    prompt = (
        f"{schema_context}\n\n"
        f"User request:\n{question}\n\n"
        f"Prior SQL:\n{prior_sql}\n\n"
        f"Database error:\n{db_error}\n\n"
        "Return corrected JSON: {\"sql\": string, \"explanation\": string}."
    )

    response = await chatbot_service.llm.ainvoke(
        [SystemMessage(content=SQL_RETRY_SYSTEM), HumanMessage(content=prompt)]
    )
    payload = parse_llm_json(str(response.content))
    return str(payload.get("sql", "")).strip(), str(payload.get("explanation", "")).strip()
