from __future__ import annotations


def select_top_opportunities(items: list[dict], limit: int) -> list[dict]:
    ranked = sorted(
        items,
        key=lambda item: (
            bool(item.get("keep")),
            float(item.get("score", 0)),
            item.get("first_seen_at") or "",
        ),
        reverse=True,
    )
    selected: list[dict] = []
    for item in ranked:
        if not item.get("keep"):
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected

