from app.services.connectors import AtomFeedSource, HTMLListingSource, JSONFeedSource, PublicProfileSource, RSSFeedSource, SitemapSource


def test_json_feed_source_collects_items(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        {
          "items": [
            {
              "canonical_name": "Alpha",
              "website_url": "https://example.com",
              "telegram_url": "https://t.me/alpha"
            }
          ]
        }
        """

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = JSONFeedSource("pump-fun", "https://example.com/feed.json", "solana")
    items = source.collect()
    assert len(items) == 1
    assert items[0]["launch_source"] == "pump-fun"
    assert items[0]["chain"] == "solana"


def test_html_listing_source_collects_items(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        <html>
          <body>
            <article data-project="Alpha" data-website="https://example.com" data-telegram="https://t.me/alpha"></article>
          </body>
        </html>
        """

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = HTMLListingSource("four-meme", "https://example.com/list", "bsc")
    items = source.collect()
    assert len(items) == 1
    assert items[0]["canonical_name"] == "Alpha"
    assert items[0]["chain"] == "bsc"


def test_public_profile_source_collects_links(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        <html>
          <head>
            <title>Alpha Profile</title>
            <meta name="description" content="Alpha social launch" />
          </head>
          <body>
            <a href="https://example.com">Website</a>
            <a href="https://t.me/alpha">Telegram</a>
            <a href="https://x.com/alpha">X</a>
          </body>
        </html>
        """

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = PublicProfileSource("alpha-x-watch", "https://x.com/alpha", "solana")
    items = source.collect()
    assert len(items) == 1
    assert items[0]["source_type"] == "social"
    assert items[0]["telegram_url"] == "https://t.me/alpha"
    assert items[0]["x_url"] == "https://x.com/alpha"


def test_rss_feed_source_collects_items(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        <rss version="2.0">
          <channel>
            <item>
              <title>Alpha launch</title>
              <link>https://example.com/alpha</link>
              <description>New website https://example.com/alpha https://t.me/alpha</description>
            </item>
          </channel>
        </rss>
        """

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = RSSFeedSource("news-feed", "https://example.com/feed.xml", "solana")
    items = source.collect()
    assert len(items) == 1
    assert items[0]["canonical_name"] == "Alpha launch"
    assert items[0]["telegram_url"] == "https://t.me/alpha"
    assert items[0]["chain"] == "solana"


def test_atom_feed_source_collects_items(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Gamma launch</title>
            <summary>New project https://example.com/gamma https://t.me/gamma</summary>
            <link rel="alternate" href="https://example.com/gamma" />
          </entry>
        </feed>
        """

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = AtomFeedSource("alpha-feed", "https://example.com/feed.atom", "solana")
    items = source.collect()

    assert len(items) == 1
    assert items[0]["canonical_name"] == "Gamma launch"
    assert items[0]["telegram_url"] == "https://t.me/gamma"
    assert items[0]["website_url"] == "https://example.com/gamma"


def test_sitemap_source_collects_items(monkeypatch) -> None:
    sitemap_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/projects/alpha</loc></url>
      <url><loc>https://example.com/projects/beta</loc></url>
    </urlset>
    """
    page_html = {
        "https://example.com/projects/alpha": """
        <html>
          <head>
            <title>Alpha Project</title>
            <meta name="description" content="Alpha meme launch" />
          </head>
          <body>
            <a href="https://t.me/alpha">Telegram</a>
            <a href="https://x.com/alpha">X</a>
          </body>
        </html>
        """,
        "https://example.com/projects/beta": """
        <html>
          <head>
            <title>Beta Project</title>
          </head>
          <body>
            <a href="https://discord.gg/beta">Discord</a>
          </body>
        </html>
        """,
    }

    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return sitemap_xml if url.endswith("sitemap.xml") else page_html[url]

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = SitemapSource("site-map", "https://example.com/sitemap.xml", "bsc")
    items = source.collect()

    assert len(items) == 2
    assert items[0]["canonical_name"] == "Alpha Project"
    assert items[0]["telegram_url"] == "https://t.me/alpha"
    assert items[1]["discord_url"] == "https://discord.gg/beta"


def test_sitemap_source_bootstraps_from_robots(monkeypatch) -> None:
    robots_text = """
    User-agent: *
    Sitemap: https://example.com/custom-sitemap.xml
    """
    sitemap_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/projects/gamma</loc></url>
    </urlset>
    """
    page_html = """
    <html>
      <head><title>Gamma Project</title></head>
      <body>
        <a href="https://t.me/gamma">Telegram</a>
      </body>
    </html>
    """

    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        if url.endswith("robots.txt"):
            return robots_text
        if url.endswith("custom-sitemap.xml"):
            return sitemap_xml
        return page_html

    monkeypatch.setattr("app.services.connectors.fetch_text", fake_fetch_text)
    source = SitemapSource("site-map", "https://example.com", "bsc")
    items = source.collect()

    assert len(items) == 1
    assert items[0]["canonical_name"] == "Gamma Project"
    assert items[0]["telegram_url"] == "https://t.me/gamma"
