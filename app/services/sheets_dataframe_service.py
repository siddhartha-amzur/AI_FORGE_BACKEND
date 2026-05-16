"""sheets_dataframe_service.py – advanced pandas-based dataframe operations.

NEW file for Project 9 Google Sheets integration.
Does NOT modify any Project 1-8 code.

Provides richer analysis operations on top of the existing
dataframe_service.py without touching it.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class DataframeAnalysisError(ValueError):
    """Raised when an unsafe or unsupported operation is requested."""


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


def _assert_safe(question: str) -> None:
    lowered = question.lower()
    for kw in _BLOCKED_KEYWORDS:
        if kw in lowered:
            raise DataframeAnalysisError(
                "Unsafe operation detected. Only read-only analytics are allowed."
            )


def build_dataframe_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a lightweight summary of *rows* without pandas dependency.

    Falls back gracefully if pandas is unavailable.
    """
    if not rows:
        return {"row_count": 0, "columns": [], "dtypes": {}, "sample": []}

    columns = list(rows[0].keys())

    # Try to compute numeric summaries via pandas
    try:
        import pandas as pd  # type: ignore

        df = pd.DataFrame(rows)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        stats: dict[str, Any] = {}
        for col in numeric_cols:
            stats[col] = {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": round(float(df[col].mean()), 4),
                "null_count": int(df[col].isna().sum()),
            }

        return {
            "row_count": len(rows),
            "columns": columns,
            "numeric_stats": stats,
            "sample": rows[:5],
        }
    except Exception:  # noqa: BLE001
        return {
            "row_count": len(rows),
            "columns": columns,
            "numeric_stats": {},
            "sample": rows[:5],
        }


def apply_dataframe_analysis(
    rows: list[dict[str, Any]],
    question: str,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Apply question-driven analysis to *rows* and return paged results.

    Supported operations (no pandas required for basic ops):
    - top N: sort descending by a numeric column and take first N rows
    - filter / only from <value>: row-level equality filter
    - sort by <column>: ascending sort
    - average / mean by <column>: group-by mean
    - count by <column>: group-by count
    - sum / total by <column>: group-by sum
    - summarize: return column summary stats
    """
    t0 = time.perf_counter()
    _assert_safe(question)

    if not rows:
        return {
            "rows": [],
            "total_rows": 0,
            "summary": "No data available.",
            "columns": [],
        }

    lowered = question.lower()
    working = list(rows)

    # --- summarize intent ---
    if any(kw in lowered for kw in ("summarize", "summary", "overview", "describe")):
        summary_data = build_dataframe_summary(working)
        result_rows = summary_data.get("sample", working[:10])
        summary_text = (
            f"Sheet has {summary_data['row_count']} rows and "
            f"{len(summary_data['columns'])} columns: "
            f"{', '.join(summary_data['columns'][:10])}."
        )
        if summary_data.get("numeric_stats"):
            for col, stats in list(summary_data["numeric_stats"].items())[:3]:
                summary_text += (
                    f" {col}: min={stats['min']}, max={stats['max']}, "
                    f"avg={stats['mean']}."
                )
        return _paginate(result_rows, summary_text, page, page_size)

    # --- filter: "only from X" ---
    if "only from" in lowered:
        target = lowered.split("only from", 1)[1].strip().split()[0].strip(",. ")
        working = [
            r for r in working
            if any(str(v).lower() == target for v in r.values() if v is not None)
        ]

    # --- aggregation via pandas ---
    agg_result = _try_pandas_aggregation(working, lowered, question)
    if agg_result is not None:
        working, summary_text = agg_result
        duration = time.perf_counter() - t0
        logger.info("[sheets_df] analysis done duration=%.4f rows=%d", duration, len(working))
        return _paginate(working, summary_text, page, page_size)

    # --- top N ---
    if "top" in lowered and working:
        n = _parse_top_n(lowered)
        numeric_col = _find_best_numeric_col(working, lowered)
        if numeric_col:
            try:
                working = sorted(
                    working,
                    key=lambda r: _to_float(r.get(numeric_col, 0)),
                    reverse=True,
                )[:n]
                summary_text = f"Top {n} rows by {numeric_col}."
            except Exception:  # noqa: BLE001
                working = working[:n]
                summary_text = f"Top {n} rows."
        else:
            working = working[:n]
            summary_text = f"Top {n} rows."
        return _paginate(working, summary_text, page, page_size)

    # --- sort ---
    if "sort by" in lowered and working:
        col_kw = lowered.split("sort by", 1)[1].strip().split()[0]
        actual = next((k for k in working[0].keys() if k.lower() == col_kw), None)
        if actual:
            working = sorted(working, key=lambda r: str(r.get(actual, "")))
            summary_text = f"Sorted by {actual} (ascending)."
        else:
            summary_text = "Could not identify sort column; showing all rows."
        return _paginate(working, summary_text, page, page_size)

    # Default: return all rows
    summary_text = f"Showing {len(working)} rows."
    duration = time.perf_counter() - t0
    logger.info("[sheets_df] default done duration=%.4f rows=%d", duration, len(working))
    return _paginate(working, summary_text, page, page_size)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate(
    rows: list[dict[str, Any]],
    summary: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    total = len(rows)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    paged = rows[start:end]
    return {
        "rows": paged,
        "total_rows": total,
        "has_more": total > end,
        "summary": summary,
        "columns": list(paged[0].keys()) if paged else [],
    }


def _to_float(val: Any) -> float:
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _parse_top_n(text: str) -> int:
    import re
    match = re.search(r"top\s+(\d+)", text)
    return int(match.group(1)) if match else 10


def _find_best_numeric_col(rows: list[dict[str, Any]], question_lower: str) -> str | None:
    if not rows:
        return None
    columns = list(rows[0].keys())
    # Prefer column name mentioned in question
    for col in columns:
        if col.lower() in question_lower:
            # Check if it looks numeric
            sample = [_to_float(r.get(col, 0)) for r in rows[:20]]
            if any(s != 0 for s in sample):
                return col
    # Fallback to first numeric-looking column
    for col in columns:
        sample = [_to_float(r.get(col, 0)) for r in rows[:20]]
        if any(s != 0 for s in sample):
            return col
    return None


def _try_pandas_aggregation(
    rows: list[dict[str, Any]],
    lowered: str,
    original_question: str,
) -> tuple[list[dict[str, Any]], str] | None:
    """Return (result_rows, summary) if a pandas aggregation matches, else None."""
    agg_keywords = {
        "average": "mean",
        "mean": "mean",
        "avg": "mean",
        "sum": "sum",
        "total": "sum",
        "count": "count",
    }
    matched_agg = next((v for k, v in agg_keywords.items() if k in lowered), None)
    if not matched_agg:
        return None

    try:
        import pandas as pd  # type: ignore

        df = pd.DataFrame(rows)
        columns = df.columns.tolist()

        # Find group-by column (after "by")
        group_col = None
        if " by " in lowered:
            by_part = lowered.split(" by ", 1)[1].strip().split()[0].strip(",.")
            group_col = next(
                (c for c in columns if c.lower() == by_part), None
            )

        # Find numeric target column (mentioned in question, before "by")
        numeric_col = None
        before_by = lowered.split(" by ")[0] if " by " in lowered else lowered
        for col in columns:
            if col.lower() in before_by:
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    if df[col].notna().any():
                        numeric_col = col
                        break
                except Exception:  # noqa: BLE001
                    pass

        # Fallback to first numeric col
        if not numeric_col:
            for col in columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    if df[col].notna().any():
                        numeric_col = col
                        break
                except Exception:  # noqa: BLE001
                    pass

        if not numeric_col:
            return None

        if group_col:
            if matched_agg == "count":
                result_df = df.groupby(group_col).size().reset_index(name="count")
                result_df = result_df.sort_values("count", ascending=False)
                summary = f"Count by {group_col}."
            else:
                result_df = (
                    df.groupby(group_col)[numeric_col]
                    .agg(matched_agg)
                    .reset_index()
                    .rename(columns={numeric_col: f"{matched_agg}_{numeric_col}"})
                )
                result_df = result_df.sort_values(
                    f"{matched_agg}_{numeric_col}", ascending=False
                )
                summary = f"{matched_agg.capitalize()} of {numeric_col} by {group_col}."
        else:
            if matched_agg == "count":
                val = len(df)
                summary = f"Total row count: {val}."
            else:
                val = round(float(df[numeric_col].agg(matched_agg)), 4)
                summary = f"{matched_agg.capitalize()} of {numeric_col}: {val}."
            return [{"result": val, "column": numeric_col, "operation": matched_agg}], summary

        result_rows = result_df.fillna("").to_dict(orient="records")
        return result_rows, summary

    except Exception as exc:  # noqa: BLE001
        logger.warning("[sheets_df] pandas aggregation failed: %s", exc)
        return None
