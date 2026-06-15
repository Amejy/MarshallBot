from app.services.extractor import extract_links, extract_social_links, hash_text


def test_extract_links_finds_social_links() -> None:
    html = """
    <html>
      <head>
        <title>Alpha</title>
        <meta name="description" content="A project">
      </head>
      <body>
        <a href="https://t.me/alpha">Telegram</a>
        <a href="https://x.com/alpha">X</a>
      </body>
    </html>
    """
    result = extract_links(html)
    assert result["title"] == "Alpha"
    assert "https://t.me/alpha" in result["telegram_links"]
    assert "https://x.com/alpha" in result["x_links"]


def test_extract_social_links_from_text() -> None:
    text = "Join https://t.me/alpha and follow https://x.com/alpha"
    result = extract_social_links(text)
    assert "https://t.me/alpha" in result["telegram"]
    assert "https://x.com/alpha" in result["x"]


def test_hash_text_stable() -> None:
    assert hash_text("hello") == hash_text("hello")
