from scripts import release_check


def test_release_check_reports_missing_values(monkeypatch, capsys) -> None:
    monkeypatch.setattr(release_check.settings, "telegram_bot_token", "")
    monkeypatch.setattr(release_check.settings, "telegram_chat_id", "")
    monkeypatch.setattr(release_check.settings, "telegram_api_id", 0)
    monkeypatch.setattr(release_check.settings, "telegram_api_hash", "")
    monkeypatch.setattr(
        release_check.SourceConfig,
        "load",
        classmethod(lambda cls: cls(launchpads=[], telegram_channels=[], social_accounts=[])),
    )

    assert release_check.main() == 1
    captured = capsys.readouterr()
    assert "Missing required environment values" in captured.out
    assert "No sources are configured" in captured.out


def test_release_check_passes_when_ready(monkeypatch, capsys) -> None:
    monkeypatch.setattr(release_check.settings, "telegram_bot_token", "token")
    monkeypatch.setattr(release_check.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(release_check.settings, "telegram_api_id", 123)
    monkeypatch.setattr(release_check.settings, "telegram_api_hash", "hash")
    monkeypatch.setattr(
        release_check.SourceConfig,
        "load",
        classmethod(lambda cls: cls(launchpads=[{"name": "pump-fun"}], telegram_channels=[], social_accounts=[])),
    )

    assert release_check.main() == 0
    captured = capsys.readouterr()
    assert "Release check passed." in captured.out
