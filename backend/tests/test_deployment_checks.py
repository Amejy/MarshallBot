from app.core.deployment import deployment_check_urls, normalize_base_url


def test_normalize_base_url_strips_trailing_slash() -> None:
    assert normalize_base_url("https://example.com/") == "https://example.com"


def test_deployment_check_urls_build_expected_paths() -> None:
    assert deployment_check_urls("https://example.com/") == [
        "https://example.com/health",
        "https://example.com/dashboard",
    ]
