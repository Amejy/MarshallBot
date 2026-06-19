from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.services.connectors import fetch_text
from app.services.extractor import extract_links
from app.services.sources import DiscoverySource


PAIR_PATH_RE = re.compile(r"^/(solana|bsc)/([A-Za-z0-9_-]{6,})/?$")


class _HrefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key.lower(): value for key, value in attrs if value is not None}
        href = attr_map.get("href")
        if href:
            self.hrefs.append(href)


def _slug_to_name(value: str) -> str:
    cleaned = value.strip().replace("-", " ").replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "DexScreener Project"


def _is_pair_url(url: str, chain: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and "dexscreener.com" not in parsed.netloc.lower():
        return False
    path = parsed.path.rstrip("/")
    return bool(PAIR_PATH_RE.match(path)) and path.startswith(f"/{chain}/")


def _pair_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    match = PAIR_PATH_RE.match(parsed.path.rstrip("/"))
    if not match:
        return "DexScreener Project"
    slug = match.group(2)
    if re.fullmatch(r"[A-Fa-f0-9]{32,}", slug):
        return "DexScreener Project"
    return _slug_to_name(slug)


class DexScreenerSource(DiscoverySource):
    def __init__(self, name: str, url: str, chain: str, limit: int = 25) -> None:
        self.name = name
        self.url = url
        self.chain = chain
        self.limit = limit

    def _pair_urls(self) -> list[str]:
        listing_html = fetch_text(self.url)
        parser = _HrefCollector()
        parser.feed(listing_html)
        pair_urls: list[str] = []
        seen: set[str] = set()
        for href in parser.hrefs:
            absolute = urljoin(self.url, href)
            if not _is_pair_url(absolute, self.chain):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            pair_urls.append(absolute)
            if len(pair_urls) >= self.limit:
                break
        return pair_urls

    def _collect_pair(self, pair_url: str) -> dict | None:
        html = fetch_text(pair_url)
        parsed = extract_links(html, base_url=pair_url)
        links = parsed.get("links") or []
        social_hosts = ("t.me/", "telegram.me/", "x.com/", "twitter.com/", "discord.gg/", "discord.com/", "dexscreener.com/")
        website_links = [link for link in links if link and not any(host in link.lower() for host in social_hosts)]
        telegram_links = parsed.get("telegram_links") or []
        x_links = parsed.get("x_links") or []
        discord_links = parsed.get("discord_links") or []
        canonical_name = parsed.get("title") or _pair_name_from_url(pair_url)
        if canonical_name:
            canonical_name = re.sub(r"\s*[\-|•]\s*DexScreener.*$", "", str(canonical_name), flags=re.IGNORECASE).strip()
        return {
            "canonical_name": canonical_name or _pair_name_from_url(pair_url),
            "chain": self.chain,
            "website_url": website_links[0] if website_links else None,
            "telegram_url": telegram_links[0] if telegram_links else None,
            "x_url": x_links[0] if x_links else None,
            "discord_url": discord_links[0] if discord_links else None,
            "launch_source": self.name,
            "source_type": "launchpad",
            "source_name": self.name,
            "dexscreener_url": pair_url,
            "raw_text": parsed.get("meta_description") or parsed.get("title") or "",
        }

    def collect(self) -> list[dict]:
        projects: list[dict] = []
        for pair_url in self._pair_urls():
            try:
                project = self._collect_pair(pair_url)
            except Exception:
                continue
            if project:
                projects.append(project)
        return projects
