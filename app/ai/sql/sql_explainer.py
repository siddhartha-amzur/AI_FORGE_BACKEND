from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.sql.prompts import SQL_EXPLANATION_SYSTEM
from app.services.chatbot import chatbot_service


async def explain_results(*, question: str, sql: str, rows: list[dict]) -> str:
    sample = rows[:10]
    prompt = (
        f"User question: {question}\n"
        f"SQL: {sql}\n"
        f"Result sample: {sample}\n"
        "Write a business-friendly summary in 1-3 sentences."
    )
    response = await chatbot_service.llm.ainvoke(
        [SystemMessage(content=SQL_EXPLANATION_SYSTEM), HumanMessage(content=prompt)]
    )
    return str(response.content).strip()
