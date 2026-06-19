from app.core.source_config import SourceConfig
from app.services.source_builder import build_source_registry
from app.services.telegram_research import _extract_website_links, _infer_project_name, build_telegram_onboarding, normalize_public_channel_name, normalize_public_channel_url


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


def test_normalize_public_channel_url_accepts_tme_links() -> None:
    assert normalize_public_channel_url("https://t.me/AlphaMemeWatch") == "AlphaMemeWatch"
    assert normalize_public_channel_url("https://t.me/s/AlphaMemeWatch") == "AlphaMemeWatch"
    assert normalize_public_channel_url("not a channel") is None


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


def test_build_source_registry_uses_public_telegram_mode() -> None:
    config = SourceConfig(
        telegram_channels=[
            {
                "name": "alpha-public",
                "enabled": True,
                "mode": "public",
                "channel": "AlphaMemeWatch",
                "chain": "solana",
                "limit": 20,
            }
        ]
    )

    registry = build_source_registry(config)
    assert "alpha-public" in registry
    assert registry["alpha-public"].__class__.__name__ == "TelegramPublicChannelSource"


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


def test_build_source_registry_uses_dexscreener_watch_mode(monkeypatch) -> None:
    def fake_fetch_text(url, timeout=20):
        if url == "https://dexscreener.com/solana":
            return """
            <html>
              <body>
                <a href="/solana/alpha123456">Alpha</a>
                <a href="/solana/beta123456">Beta</a>
              </body>
            </html>
            """
        if url.endswith("/solana/alpha123456"):
            return """
            <html>
              <head><title>Alpha Wolf | DexScreener</title></head>
              <body>
                <a href="https://alpha.wtf">Website</a>
                <a href="https://t.me/alpha">Telegram</a>
              </body>
            </html>
            """
        if url.endswith("/solana/beta123456"):
            return """
            <html>
              <head><title>Beta Moon | DexScreener</title></head>
              <body>
                <a href="https://beta.wtf">Website</a>
                <a href="https://t.me/beta">Telegram</a>
              </body>
            </html>
            """
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr("app.services.dexscreener.fetch_text", fake_fetch_text)

    config = SourceConfig(
        social_accounts=[
            {
                "name": "dexscreener-solana-watch",
                "enabled": True,
                "mode": "profile",
                "chain": "solana",
                "url": "https://dexscreener.com/solana",
                "limit": 2,
            }
        ]
    )

    registry = build_source_registry(config)
    assert "dexscreener-solana-watch" in registry
    items = registry["dexscreener-solana-watch"].collect()
    assert len(items) == 2
    assert items[0]["canonical_name"] == "Alpha Wolf"
    assert items[0]["website_url"] == "https://alpha.wtf"
    assert items[0]["telegram_url"] == "https://t.me/alpha"


def test_public_telegram_channel_source_collects_quality_items(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.telegram_research.fetch_text",
        lambda url, timeout=20: """
        <html>
          <body>
            <div class="tgme_widget_message_text js-message_text" dir="auto">
              Alpha launch https://alpha.io <a href="https://t.me/alpha">Telegram</a>
            </div>
            <div class="tgme_widget_message_text js-message_text" dir="auto">
              Missing website <a href="https://t.me/nope">Telegram</a>
            </div>
          </body>
        </html>
        """,
    )

    from app.services.telegram_research import TelegramPublicChannelSource

    source = TelegramPublicChannelSource("alpha-public", "AlphaMemeWatch", chain="solana", limit=10)
    items = source.collect()

    assert len(items) == 1
    assert items[0]["canonical_name"] == "Alpha launch"
    assert items[0]["website_url"] == "https://alpha.io"
    assert items[0]["telegram_url"] == "https://t.me/alpha"
    assert items[0]["source_type"] == "telegram"
