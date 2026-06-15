from app.services.enrichment import website_quality_score
from app.services.enrichment import enrich_website
from app.services.filters import looks_like_spam, spam_penalty


def test_spam_penalty_flags_obvious_promotional_language() -> None:
    project = {
        "canonical_name": "Free Airdrop Win",
        "launch_source": "telegram",
        "raw_text": "double your money with this giveaway",
        "website_url": "https://example.com",
        "telegram_url": "https://t.me/example",
    }

    assert spam_penalty(project) >= 40.0
    assert looks_like_spam(project) is True


def test_website_quality_score_rewards_rich_pages() -> None:
    parsed_data = {
        "title": "Alpha",
        "meta_description": "Community first meme launch",
        "telegram_links": ["https://t.me/alpha"],
        "x_links": ["https://x.com/alpha"],
        "discord_links": [],
        "links": ["https://example.com", "https://t.me/alpha", "https://x.com/alpha"],
        "word_count": 75,
        "content_length": 1600,
    }

    assert website_quality_score(parsed_data) > 60.0


def test_website_quality_score_rewards_bsc_chain_terms() -> None:
    parsed_data = {
        "title": "Alpha BSC",
        "meta_description": "Launchpad on BNB Chain",
        "telegram_links": ["https://t.me/alpha"],
        "x_links": ["https://x.com/alpha"],
        "discord_links": [],
        "links": ["https://pancakeswap.finance", "https://www.bscscan.com", "https://alpha.io"],
        "word_count": 18,
        "content_length": 620,
    }

    assert website_quality_score(parsed_data, chain="bsc") > website_quality_score(parsed_data, chain=None)


def test_website_quality_score_rewards_solana_chain_terms() -> None:
    parsed_data = {
        "title": "Alpha Solana",
        "meta_description": "A community token for Solana traders",
        "telegram_links": ["https://t.me/alpha"],
        "x_links": ["https://x.com/alpha"],
        "discord_links": [],
        "links": ["https://jupiter.exchange", "https://solscan.io", "https://alpha.io"],
        "word_count": 18,
        "content_length": 620,
    }

    assert website_quality_score(parsed_data, chain="solana") > website_quality_score(parsed_data, chain=None)


def test_enrich_website_uses_rendered_content(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch_url",
        lambda url: (
            "<html><head><title>Alpha</title></head><body><a href='https://example.com'>Site</a></body></html>",
            {"content_type": "text/html", "charset": "utf-8"},
        ),
    )
    monkeypatch.setattr(
        "app.services.enrichment.render_website",
        lambda url, screenshot_dir=None, timeout=15000: {
            "html": "<html><head><title>Alpha Rendered</title></head><body><a href='https://t.me/alpha'>Telegram</a></body></html>",
            "title": "Alpha Rendered",
            "screenshot_path": "/tmp/alpha.png",
        },
    )

    enrichment = enrich_website("https://example.com")

    assert enrichment["title"] == "Alpha Rendered"
    assert enrichment["screenshot_path"] == "/tmp/alpha.png"
    assert "https://t.me/alpha" in enrichment["parsed_data"]["telegram_links"]
