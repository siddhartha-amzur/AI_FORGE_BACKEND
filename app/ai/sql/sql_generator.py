from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.sql.prompts import SQL_GENERATION_SYSTEM
from app.ai.sql.utils import parse_llm_json
from app.services.chatbot import chatbot_service


async def generate_sql(*, question: str, schema_context: str, memory_context: str) -> tuple[str, str]:
    prompt = (
        f"{schema_context}\n\n"
        f"Conversation SQL memory:\n{memory_context or 'None'}\n\n"
        f"User request:\n{question}\n\n"
        "Return JSON: {\"sql\": string, \"explanation\": string}."
    )

    response = await chatbot_service.llm.ainvoke(
        [
            SystemMessage(content=SQL_GENERATION_SYSTEM),
            HumanMessage(content=prompt),
        ]
    )
    payload = parse_llm_json(str(response.content))
    return str(payload.get("sql", "")).strip(), str(payload.get("explanation", "")).strip()
