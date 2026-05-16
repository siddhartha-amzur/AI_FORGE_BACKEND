from __future__ import annotations

import re


FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "comment",
    "copy",
}


class SQLSafetyError(ValueError):
    pass


def normalize_sql(sql: str) -> str:
    sql = sql.strip().rstrip(";")
    return sql


def ensure_read_only_sql(sql: str) -> str:
    normalized = normalize_sql(sql)
    lowered = normalized.lower().strip()

    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise SQLSafetyError("Only SELECT and WITH queries are allowed")

    if ";" in normalized:
        raise SQLSafetyError("Multiple statements are not allowed")

    tokens = set(re.findall(r"\b[a-z_]+\b", lowered))
    blocked = tokens.intersection(FORBIDDEN_KEYWORDS)
    if blocked:
        raise SQLSafetyError("Unsafe SQL keyword detected")

    return normalized
