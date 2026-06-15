from app.services.orchestration import process_source
from app.services.ranking import RankingConfig
from app.services.sources import StaticDiscoverySource


def test_process_source_can_skip_recently_scored(monkeypatch) -> None:
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

    monkeypatch.setattr("app.services.orchestration.project_scored_recently", lambda project_id, within_minutes=30: True)
    results = process_source(source, RankingConfig(min_score_to_alert=0), enrich_websites=False)
    assert results[0]["skipped_reason"] == "recently_scored"

