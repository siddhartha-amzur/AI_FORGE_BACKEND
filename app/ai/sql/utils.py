from __future__ import annotations

import json
import re


def _extract_select_sql(text: str) -> str:
    code_blocks = re.findall(r"```(?:sql|postgresql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    for block in code_blocks:
        candidate = block.strip().rstrip(";")
        if candidate.lower().startswith("select"):
            return candidate

    match = re.search(r"(select\b[\s\S]*?)(?:;|$)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip(";")

    return ""


def parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    json_blocks = re.findall(r"```json\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    for block in json_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    sql = _extract_select_sql(raw)
    if sql:
        explanation = raw.replace(sql, "").strip()
        return {"sql": sql, "explanation": explanation or "Generated SQL query"}

    raise ValueError("LLM response could not be parsed into SQL JSON")
