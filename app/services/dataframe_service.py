from __future__ import annotations

import time
from typing import Any

from app.ai.sql.dataframe_analyzer import summarize_rows


def apply_safe_dataframe_analysis(rows: list[dict[str, Any]], question: str) -> dict[str, Any]:
    start = time.perf_counter()
    lowered = question.lower()

    # Hard-block arbitrary execution attempts.
    blocked_keywords = ["eval(", "exec(", "__import__", "lambda", "subprocess", "os.system"]
    if any(keyword in lowered for keyword in blocked_keywords):
        raise ValueError("Unsafe operation requested. Only filtering, grouping, aggregation and sorting are allowed.")

    working_rows = rows

    # Simple deterministic filtering support for follow-ups like "only from Texas".
    if "only from" in lowered:
        target = lowered.split("only from", 1)[1].strip().split()[0].strip(",. ")
        if target:
            target_l = target.lower()
            filtered = []
            for row in working_rows:
                if any(str(value).lower() == target_l for value in row.values() if value is not None):
                    filtered.append(row)
            working_rows = filtered

    # Basic sort support.
    if "sort by" in lowered and working_rows:
        column = lowered.split("sort by", 1)[1].strip().split()[0]
        actual = next((key for key in working_rows[0].keys() if key.lower() == column.lower()), None)
        if actual:
            working_rows = sorted(working_rows, key=lambda item: str(item.get(actual, "")))

    analysis = summarize_rows(working_rows)
    analysis["rows"] = working_rows
    duration = time.perf_counter() - start
    print(f"[dataframe_processing] duration_seconds={duration:.4f}")
    return analysis
