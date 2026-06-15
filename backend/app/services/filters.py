from __future__ import annotations

import re
from urllib.parse import urlparse


SPAM_PATTERNS = (
    re.compile(r"\bairdrop\b", re.IGNORECASE),
    re.compile(r"\bgiveaway\b", re.IGNORECASE),
    re.compile(r"\bfree\s+claim\b", re.IGNORECASE),
    re.compile(r"\bdouble\s+your\s+money\b", re.IGNORECASE),
    re.compile(r"\bwallet\s+connect\b", re.IGNORECASE),
    re.compile(r"\bwhatsapp\b", re.IGNORECASE),
    re.compile(r"\btest\s*token\b", re.IGNORECASE),
)


def _normalized_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def passes_hard_filters(project: dict, blacklisted_domains: list[str] | None = None, blacklisted_telegram: list[str] | None = None) -> bool:
    if not project.get("website_url"):
        return False
    if not project.get("telegram_url"):
        return False
    if project.get("status") in {"duplicate", "rejected"}:
        return False
    if project.get("duplicate_of_project_id"):
        return False
    if blacklisted_domains:
        domain = _normalized_domain(project.get("website_url"))
        if domain and domain in {item.lower().strip() for item in blacklisted_domains}:
            return False
    if blacklisted_telegram:
        telegram_url = str(project.get("telegram_url") or "").strip().lower()
        if telegram_url in {item.lower().strip() for item in blacklisted_telegram}:
            return False
    return True


def spam_penalty(project: dict) -> float:
    text_parts = [
        str(project.get("canonical_name", "")),
        str(project.get("launch_source", "")),
        str(project.get("raw_text", "")),
        str(project.get("website_url", "")),
        str(project.get("telegram_url", "")),
        str(project.get("x_url", "")),
        str(project.get("discord_url", "")),
    ]
    combined = " ".join(text_parts).lower()
    penalty = 0.0
    for pattern in SPAM_PATTERNS:
        if pattern.search(combined):
            penalty += 20.0
    if "pump.fun" in combined and "airdrop" in combined:
        penalty += 10.0
    if len(combined.split()) < 3:
        penalty += 5.0
    return min(100.0, penalty)


def looks_like_spam(project: dict) -> bool:
    return spam_penalty(project) >= 40.0
