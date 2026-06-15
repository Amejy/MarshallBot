from app.core.source_config import SourceConfig
from app.services.backfill import backfill_source
from app.services.ranking import RankingConfig
from app.services.sources import StaticDiscoverySource


def test_backfill_source_returns_counts(monkeypatch) -> None:
    from app.services import backfill as backfill_module

    monkeypatch.setattr(
        backfill_module,
        "build_default_registry",
        lambda source_config: {"sample": StaticDiscoverySource([{"canonical_name": "Alpha", "chain": "solana", "website_url": "https://example.com", "telegram_url": "https://t.me/example", "source_type": "demo", "source_name": "demo"}])},
    )
    result = backfill_source("sample", SourceConfig(), RankingConfig(min_score_to_alert=0))
    assert result["count"] == 1

