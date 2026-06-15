from __future__ import annotations


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def deployment_check_urls(base_url: str) -> list[str]:
    normalized = normalize_base_url(base_url)
    return [f"{normalized}/health", f"{normalized}/dashboard"]
