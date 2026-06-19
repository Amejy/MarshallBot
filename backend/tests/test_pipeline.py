from datetime import datetime, timezone, timedelta

from app.services.pipeline import build_default_signals, evaluate_project, ingest_discovery_event, normalize_event
from app.core.source_config import SourceConfig
from app.services.decision import should_keep_project
from app.services.ranking import RankingConfig


def test_normalize_event_defaults() -> None:
    event = normalize_event(
        {
            "canonical_name": "PepeX",
            "chain": "solana",
            "website_url": "https://example.com",
            "telegram_url": "https://t.me/example",
        }
    )
    assert event["launch_source"] == "unknown"
    assert event["status"] == "new"


def test_evaluate_project_returns_score_payload() -> None:
    project = {
        "id": 1,
        "canonical_name": "PepeX",
        "chain": "solana",
        "website_url": "https://example.com",
        "telegram_url": "https://t.me/example",
        "x_url": None,
        "discord_url": None,
        "launch_source": "launchpad",
        "first_seen_at": "2026-06-10T00:00:00Z",
    }
    result = evaluate_project(
        project,
        {
            "freshness": 80,
            "telegram_presence": 80,
            "social_activity": 50,
            "website_quality": 50,
            "growth_rate": 40,
            "source_quality": 60,
            "community_activity": 45,
            "spam_penalty": 0,
        },
    )
    assert result["project_id"] == 1
    assert result["score"] > 0
    assert result["score_explanations"]
    assert "explanations" in result["score_reasons"]


def test_build_default_signals_rewards_launchpad_sources() -> None:
    signals = build_default_signals(
        {
            "canonical_name": "Alpha",
            "chain": "bsc",
            "launch_source": "four-meme",
            "source_type": "launchpad",
            "source_name": "four-meme",
            "telegram_url": "https://t.me/alpha",
            "website_url": "https://alpha.io",
            "x_url": "https://x.com/alpha",
        },
        project={
            "chain": "bsc",
            "telegram_url": "https://t.me/alpha",
            "website_url": "https://alpha.io",
            "x_url": "https://x.com/alpha",
        },
        source_config=SourceConfig(trusted_sources=["four-meme"]),
    )

    assert signals["source_quality"] >= 80
    assert signals["growth_rate"] >= 45
    assert signals["telegram_presence"] == 92
    assert signals["community_activity"] >= 50
    assert signals["social_activity"] >= 60


def test_build_default_signals_keeps_research_sources_distinct() -> None:
    signals = build_default_signals(
        {
            "canonical_name": "Alpha",
            "chain": "solana",
            "launch_source": "alpha-meme-watch",
            "source_type": "telegram",
            "source_name": "alpha-meme-watch",
            "telegram_url": "https://t.me/alpha",
        },
        project={
            "chain": "solana",
            "telegram_url": "https://t.me/alpha",
        },
        source_config=SourceConfig(trusted_sources=["alpha-meme-watch"]),
    )

    assert signals["source_quality"] >= 80
    assert signals["freshness"] >= 80
    assert signals["community_activity"] >= 50


def test_build_default_signals_rewards_multiple_social_channels() -> None:
    signals = build_default_signals(
        {
            "canonical_name": "Alpha",
            "chain": "solana",
            "launch_source": "pump-fun",
            "source_type": "launchpad",
            "source_name": "pump-fun",
            "telegram_url": "https://t.me/alpha",
            "x_url": "https://x.com/alpha",
            "discord_url": "https://discord.gg/alpha",
            "raw_text": "community holders raid launch now tokenomics roadmap",
        },
        project={
            "chain": "solana",
            "telegram_url": "https://t.me/alpha",
            "x_url": "https://x.com/alpha",
            "discord_url": "https://discord.gg/alpha",
        },
        source_config=SourceConfig(trusted_sources=["pump-fun"]),
    )

    assert signals["social_activity"] >= 80
    assert signals["community_activity"] >= 70


def test_build_default_signals_uses_pair_age_for_freshness() -> None:
    pair_created_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    signals = build_default_signals(
        {
            "canonical_name": "FreshToken",
            "chain": "solana",
            "launch_source": "dexscreener-solana-watch",
            "source_type": "launchpad",
            "source_name": "dexscreener-solana-watch",
        },
        project={
            "chain": "solana",
            "pair_created_at": pair_created_at,
            "telegram_url": "https://t.me/fresh",
            "website_url": "https://fresh.example",
        },
        source_config=SourceConfig(trusted_sources=["dexscreener-solana-watch"]),
    )

    assert signals["project_age_hours"] is not None
    assert signals["freshness"] >= 90


def test_should_keep_project_rejects_old_projects() -> None:
    assert not should_keep_project(
        {"project_age_hours": 72.1, "website_url": "https://example.com", "telegram_url": "https://t.me/example"},
        95.0,
        RankingConfig(max_project_age_hours=24.0),
    )
