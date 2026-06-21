from pathlib import Path

from app.core.config import settings
from app.core.config import Settings
from app.core.source_config import SourceConfig, build_source_coverage_summary, build_source_selection_summary


def test_source_config_loads_missing_file(tmp_path: Path) -> None:
    from app.core.config import settings

    settings.launchpad_sources = []
    settings.telegram_channels = []
    settings.social_accounts = []
    config = SourceConfig.load(tmp_path / "missing.json")
    assert config.launchpads == []
    assert config.telegram_channels == []
    assert config.social_accounts == []
    assert config.keywords == []


def test_settings_parses_csv_and_json_lists(monkeypatch) -> None:
    monkeypatch.setenv("telegram_channels", "alpha-meme-watch, dexscreener-solana-watch")
    monkeypatch.setenv("social_accounts", '["bsc-social-watch", "dexscreener-bsc-watch"]')
    parsed = Settings(_env_file=None)

    assert parsed.telegram_channels == ["alpha-meme-watch", "dexscreener-solana-watch"]
    assert parsed.social_accounts == ["bsc-social-watch", "dexscreener-bsc-watch"]


def test_source_config_loads_default_sources_file() -> None:
    config = SourceConfig.load("config/sources.json")
    assert any(item.get("name") == "pump-fun" for item in config.launchpads)
    assert any(item.get("name") == "four-meme" and item.get("mode") == "fourmeme" for item in config.launchpads)
    assert any(item.get("name") == "bnb-chain-news" and item.get("mode") == "sitemap" for item in config.launchpads)
    assert any(item.get("name") == "alpha-meme-watch" and item.get("mode") == "research" for item in config.telegram_channels)
    assert any(item.get("name") == "bsc-social-watch" and item.get("mode") == "profile" for item in config.social_accounts)
    assert any(item.get("name") == "pumpfun-x-watch" and item.get("mode") == "profile" for item in config.social_accounts)
    assert any(item.get("name") == "dexscreener-x-watch" and item.get("mode") == "profile" for item in config.social_accounts)
    assert any(item.get("name") == "dexscreener-solana-watch" and item.get("mode") == "profile" for item in config.social_accounts)
    assert any(item.get("name") == "dexscreener-bsc-watch" and item.get("mode") == "profile" for item in config.social_accounts)
    assert any(item.get("name") == "dexscreener-solana-newpairs" and item.get("mode") == "newpairs" for item in config.social_accounts)
    assert any(item.get("name") == "dexscreener-bsc-newpairs" and item.get("mode") == "newpairs" for item in config.social_accounts)
    assert "pump-fun" in config.trusted_sources


def test_source_config_merges_env_selected_presets(monkeypatch) -> None:
    monkeypatch.setattr(settings, "launchpad_sources", ["pump-fun", "solana-homepages", "four-meme"])
    monkeypatch.setattr(settings, "telegram_channels", ["alpha-meme-watch"])
    monkeypatch.setattr(settings, "social_accounts", ["alpha-x-watch"])

    config = SourceConfig.load(Path("/tmp/does-not-exist.json"))

    assert [item.get("name") for item in config.launchpads] == ["pump-fun", "solana-homepages", "four-meme"]
    assert [item.get("name") for item in config.telegram_channels] == ["alpha-meme-watch"]
    assert [item.get("name") for item in config.social_accounts] == ["alpha-x-watch"]


def test_build_source_selection_summary_reports_active_items(monkeypatch) -> None:
    monkeypatch.setattr(settings, "launchpad_sources", ["pump-fun"])
    monkeypatch.setattr(settings, "telegram_channels", ["alpha-meme-watch"])
    monkeypatch.setattr(settings, "social_accounts", ["alpha-x-watch"])

    config = SourceConfig(
        launchpads=[{"name": "pump-fun"}, {"name": "custom-feed"}],
        telegram_channels=[{"name": "alpha-meme-watch"}],
        social_accounts=[{"name": "alpha-x-watch"}],
        keywords=["meme"],
        trusted_sources=["pump-fun"],
    )
    summary = build_source_selection_summary(config)

    assert summary["launchpads"]["active"] == ["pump-fun", "custom-feed"]
    assert summary["telegram_channels"]["active"] == ["alpha-meme-watch"]
    assert summary["social_accounts"]["active"] == ["alpha-x-watch"]
    assert summary["keywords"] == ["meme"]


def test_build_source_coverage_summary_marks_ready(monkeypatch) -> None:
    monkeypatch.setattr(settings, "launchpad_sources", ["pump-fun"])
    monkeypatch.setattr(settings, "telegram_channels", ["alpha-meme-watch"])
    monkeypatch.setattr(settings, "social_accounts", ["alpha-x-watch"])

    config = SourceConfig(
        launchpads=[{"name": "pump-fun"}],
        telegram_channels=[{"name": "alpha-meme-watch"}],
        social_accounts=[{"name": "alpha-x-watch"}],
        keywords=["meme"],
        trusted_sources=["pump-fun"],
    )
    summary = build_source_coverage_summary(config, templates_count=9)

    assert summary["ready"] is True
    assert summary["active_sources"] == 3
    assert summary["active_social_accounts"] == 1
    assert summary["source_templates"] == 9
