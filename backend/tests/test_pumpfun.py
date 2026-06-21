from app.services.pumpfun import PumpFunSource, _parse_age_minutes, _parse_market_cap, enrich_pumpfun_project


def test_parse_market_cap() -> None:
    assert _parse_market_cap("$ 5.00K MC") == 5000.0
    assert _parse_market_cap("$ 8.12M MC") == 8_120_000.0


def test_parse_age_minutes() -> None:
    assert _parse_age_minutes("Molecoin $MOLE $ 5.00K MC 8m") == 8.0
    assert _parse_age_minutes("Fresh token 2h") == 120.0


def test_pumpfun_source_collects_items(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        <html>
          <body>
            <a href="/coin/ABC123">Molecoin $MOLE $ 5.00K MC DD8G5t 8m</a>
            <a href="/coin/XYZ789">Dark Triad $DARKTRIAD $ 8.12K MC 5ZqkAf 4m</a>
          </body>
        </html>
        """

    monkeypatch.setattr("app.services.pumpfun.fetch_text", fake_fetch_text)
    source = PumpFunSource()
    items = source.collect()
    assert len(items) == 2
    assert items[0]["launch_source"] == "pump-fun"
    assert items[0]["chain"] == "solana"
    assert items[0]["pumpfun_url"].endswith("/coin/XYZ789")
    assert items[0]["project_age_minutes"] == 4.0
    assert items[1]["project_age_minutes"] == 8.0


def test_enrich_pumpfun_project_extracts_links(monkeypatch) -> None:
    def fake_fetch_text(url: str, timeout: int = 20) -> str:
        return """
        <html>
          <head>
            <title>MOLE</title>
          </head>
          <body>
            <a href="https://example.com">Website</a>
            <a href="https://t.me/mole">Telegram</a>
            <a href="https://x.com/mole">X</a>
          </body>
        </html>
        """

    monkeypatch.setattr("app.services.pumpfun.fetch_text", fake_fetch_text)
    project = {
        "canonical_name": "MOLE",
        "pumpfun_url": "https://pump.fun/coin/ABC123",
        "launch_source": "pump-fun",
    }
    enriched = enrich_pumpfun_project(project)
    assert enriched["website_url"] == "https://example.com"
    assert enriched["telegram_url"] == "https://t.me/mole"
    assert enriched["x_url"] == "https://x.com/mole"
