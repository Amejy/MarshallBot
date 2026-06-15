from app.core.tunnel import extract_tunnel_url


def test_extract_tunnel_url_finds_trycloudflare_domain() -> None:
    line = "INF Requesting new quick Tunnel on https://gentle-moon-123.trycloudflare.com"

    assert extract_tunnel_url(line) == "https://gentle-moon-123.trycloudflare.com"


def test_extract_tunnel_url_returns_none_when_missing() -> None:
    assert extract_tunnel_url("no tunnel url here") is None
