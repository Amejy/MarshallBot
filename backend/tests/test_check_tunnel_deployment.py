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

    def fake_urlopen(url, timeout=15):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return Response()

    with patch("scripts.check_tunnel_deployment.urlopen", side_effect=fake_urlopen):
        assert check_tunnel_deployment.main() == 1

    captured = capsys.readouterr()
    assert "No Cloudflare Tunnel URL found" in captured.err


def test_check_tunnel_deployment_validates_local_health_first(monkeypatch, capsys) -> None:
    stream = StringIO("https://bright-sky-123.trycloudflare.com\n")
    monkeypatch.setattr("sys.stdin", stream)

    def fake_urlopen(url, timeout=15):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        assert url.startswith("http://127.0.0.1:8000")
        return Response()

    with patch("scripts.check_tunnel_deployment.urlopen", side_effect=fake_urlopen):
        assert check_tunnel_deployment.main() == 0

    captured = capsys.readouterr()
    assert "OK 200 http://127.0.0.1:8000/health" in captured.out
    assert "OK 200 http://127.0.0.1:8000/dashboard" in captured.out
