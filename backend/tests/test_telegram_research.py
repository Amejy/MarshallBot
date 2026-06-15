from app.core.source_config import SourceConfig
from app.services.source_builder import build_source_registry
from app.services.telegram_research import _extract_website_links, _infer_project_name, build_telegram_onboarding, normalize_public_channel_name


def test_infer_project_name_uses_first_line() -> None:
    assert _infer_project_name("ALPHA | fair launch\nmore text", "fallback") == "ALPHA"


def test_extract_website_links_filters_social_links() -> None:
    text = "website https://example.com Telegram https://t.me/example X https://x.com/example"
    links = _extract_website_links(text)
    assert links == ["https://example.com"]


def test_normalize_public_channel_name_accepts_handles() -> None:
    assert normalize_public_channel_name("@AlphaMemeWatch") == "AlphaMemeWatch"
    assert normalize_public_channel_name("AlphaMemeWatch") == "AlphaMemeWatch"
    assert normalize_public_channel_name("bad handle!") is None


def test_build_telegram_onboarding_returns_example_config() -> None:
    onboarding = build_telegram_onboarding(["@AlphaMemeWatch", "bad handle!", "Beta_Watch"], chain="solana")

    assert onboarding["channels"] == ["AlphaMemeWatch", "Beta_Watch"]
    assert onboarding["invalid_channels"] == ["bad handle!"]
    assert onboarding["example_json"]["mode"] == "research"


def test_build_source_registry_uses_telegram_research_mode() -> None:
    config = SourceConfig(
        telegram_channels=[
            {
                "name": "alpha-research",
                "enabled": True,
                "mode": "research",
                "channels": ["alpha_channel"],
                "chain": "solana",
                "limit": 25,
            }
        ]
    )

    registry = build_source_registry(config)
    assert "alpha-research" in registry
    assert registry["alpha-research"].__class__.__name__ == "TelegramResearchSource"


def test_build_source_registry_uses_fourmeme_mode() -> None:
    config = SourceConfig(
        launchpads=[
            {
                "name": "alpha-site",
                "enabled": True,
                "mode": "fourmeme",
                "url": "https://four.meme",
                "chain": "bsc",
                "limit": 10,
            }
        ]
    )

    registry = build_source_registry(config)
    assert "alpha-site" in registry
    assert registry["alpha-site"].__class__.__name__ == "FourMemeSource"


def test_build_source_registry_uses_atom_mode() -> None:
    config = SourceConfig(
        launchpads=[
            {
                "name": "alpha-feed",
                "enabled": True,
                "mode": "atom",
                "url": "https://example.com/feed.atom",
                "chain": "solana",
            }
        ]
    )

    registry = build_source_registry(config)
    assert "alpha-feed" in registry
    assert registry["alpha-feed"].__class__.__name__ == "AtomFeedSource"


def test_build_source_registry_uses_social_rss_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.connectors.fetch_text",
        lambda url, timeout=20: "<rss version='2.0'><channel></channel></rss>",
    )
    config = SourceConfig(
        social_accounts=[
            {
                "name": "alpha-x-watch",
                "enabled": True,
                "mode": "rss",
                "chain": "solana",
                "url": "https://example.com/feed.xml",
                "limit": 25,
            }
        ]
    )

    registry = build_source_registry(config)
    assert "alpha-x-watch" in registry
    assert registry["alpha-x-watch"].collect() == []


def test_build_source_registry_uses_social_profile_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.connectors.fetch_text",
        lambda url, timeout=20: """
        <html>
          <head><title>Alpha Profile</title></head>
          <body>
            <a href="https://example.com">Website</a>
            <a href="https://t.me/alpha">Telegram</a>
          </body>
        </html>
        """,
    )
    config = SourceConfig(
        social_accounts=[
            {
                "name": "alpha-x-watch",
                "enabled": True,
                "mode": "profile",
                "chain": "solana",
                "url": "https://x.com/alpha",
                "limit": 25,
            }
        ]
    )

    registry = build_source_registry(config)
    assert "alpha-x-watch" in registry
    items = registry["alpha-x-watch"].collect()
    assert items[0]["source_type"] == "social"
    assert items[0]["telegram_url"] == "https://t.me/alpha"
