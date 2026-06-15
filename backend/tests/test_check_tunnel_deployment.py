from io import StringIO
from unittest.mock import patch

from scripts import check_tunnel_deployment


def test_check_tunnel_deployment_reports_healthy_url(monkeypatch, capsys) -> None:
    stream = StringIO("noise\nhttps://bright-sky-123.trycloudflare.com\n")
    monkeypatch.setattr("sys.stdin", stream)

    with patch("scripts.check_tunnel_deployment.urlopen") as urlopen_mock:
        urlopen_mock.return_value.__enter__.return_value.status = 200
        assert check_tunnel_deployment.main() == 0

    captured = capsys.readouterr()
    assert "Tunnel URL found: https://bright-sky-123.trycloudflare.com" in captured.out
    assert "Deployment is healthy" in captured.out


def test_check_tunnel_deployment_errors_when_missing_url(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("noise only\n"))

    assert check_tunnel_deployment.main() == 1
    captured = capsys.readouterr()
    assert "No Cloudflare Tunnel URL found" in captured.err
