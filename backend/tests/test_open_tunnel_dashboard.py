from unittest.mock import patch

from scripts import open_tunnel_dashboard


def test_open_tunnel_dashboard_prints_dashboard_url(monkeypatch, capsys) -> None:
    lines = iter(["noise", "https://bright-sky-123.trycloudflare.com\n"])
    monkeypatch.setattr("sys.stdin", lines)

    with patch("scripts.open_tunnel_dashboard.webbrowser.open") as open_mock:
        assert open_tunnel_dashboard.main() == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == "https://bright-sky-123.trycloudflare.com/dashboard"
    open_mock.assert_called_once_with("https://bright-sky-123.trycloudflare.com/dashboard")
