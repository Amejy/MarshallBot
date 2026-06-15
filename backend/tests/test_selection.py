from app.services.selection import select_top_opportunities


def test_select_top_opportunities_respects_limit() -> None:
    items = [
        {"keep": True, "score": 60, "first_seen_at": "2026-06-10T10:00:00Z"},
        {"keep": True, "score": 90, "first_seen_at": "2026-06-10T09:00:00Z"},
        {"keep": False, "score": 100, "first_seen_at": "2026-06-10T08:00:00Z"},
        {"keep": True, "score": 70, "first_seen_at": "2026-06-10T11:00:00Z"},
    ]
    selected = select_top_opportunities(items, limit=2)
    assert len(selected) == 2
    assert selected[0]["score"] == 90
    assert selected[1]["score"] == 70

