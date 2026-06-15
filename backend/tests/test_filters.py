from app.services.filters import passes_hard_filters


def test_passes_hard_filters_rejects_duplicate_projects() -> None:
    project = {
        "website_url": "https://example.com",
        "telegram_url": "https://t.me/example",
        "duplicate_of_project_id": 42,
    }

    assert passes_hard_filters(project) is False
