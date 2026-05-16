from __future__ import annotations


def pick_relevant_tables(question: str, available_tables: list[str], max_tables: int = 8) -> list[str]:
    if not available_tables:
        return []

    lowered = question.lower()
    scored: list[tuple[int, str]] = []
    for table in available_tables:
        score = 0
        table_tokens = table.lower().replace("_", " ").split()
        for token in table_tokens:
            if token and token in lowered:
                score += 2
        if table.lower() in lowered:
            score += 3
        scored.append((score, table))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [table for score, table in scored if score > 0][:max_tables]
    if selected:
        return selected
    return available_tables[:max_tables]
