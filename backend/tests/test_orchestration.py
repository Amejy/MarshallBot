from app.services.orchestration import process_source
from app.services.ranking import RankingConfig
from app.services.sources import StaticDiscoverySource


def test_process_source_marks_items() -> None:
    source = StaticDiscoverySource(
        [
            {
                "canonical_name": "Alpha",
                "chain": "solana",
                "website_url": "https://example.com",
                "telegram_url": "https://t.me/example",
                "source_type": "demo",
                "source_name": "demo",
            }
        ]
    )
    results = process_source(source, RankingConfig(min_score_to_alert=0))
    assert len(results) == 1
    assert "score" in results[0]
    assert "keep" in results[0]


def test_process_source_exposes_source_trust_movement(monkeypatch) -> None:
    source = StaticDiscoverySource(
        [
            {
                "canonical_name": "Alpha",
                "chain": "solana",
                "website_url": "https://example.com",
                "telegram_url": "https://t.me/example",
                "source_type": "demo",
                "source_name": "demo",
            }
        ]
    )
    monkeypatch.setattr(
        "app.services.orchestration.adjust_source_trust",
        lambda *args, **kwargs: 62.5,
    )
    results = process_source(source, RankingConfig(min_score_to_alert=0))
    assert results[0]["source_trust_movement"] == 12.5
    assert results[0]["source_trust_movement_direction"] == "up"


def test_process_source_persists_social_profiles(monkeypatch) -> None:
    source = StaticDiscoverySource(
        [
            {
                "canonical_name": "Alpha",
                "chain": "solana",
                "website_url": "https://example.com",
                "telegram_url": "https://t.me/example",
                "x_url": "https://x.com/example",
                "discord_url": "https://discord.gg/example",
                "source_type": "demo",
                "source_name": "demo",
            }
        ]
    )
    calls: list[tuple[str, str, str]] = []

    def fake_upsert_social_profile(project_id: int, platform: str, url: str, **kwargs) -> dict:
        calls.append((str(project_id), platform, url))
        return {"project_id": project_id, "platform": platform, "url": url}

    monkeypatch.setattr("app.services.orchestration.upsert_social_profile", fake_upsert_social_profile)
    process_source(source, RankingConfig(min_score_to_alert=0))

    assert ("telegram", "https://t.me/example") in {(platform, url) for _, platform, url in calls}
    assert ("x", "https://x.com/example") in {(platform, url) for _, platform, url in calls}
    assert ("discord", "https://discord.gg/example") in {(platform, url) for _, platform, url in calls}
