from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


SOCIAL_PATTERNS = {
    "telegram": re.compile(r"https?://(?:t\.me|telegram\.me)/[^\s\"'<>]+", re.IGNORECASE),
    "x": re.compile(r"https?://(?:x\.com|twitter\.com)/[^\s\"'<>]+", re.IGNORECASE),
    "discord": re.compile(r"https?://(?:discord\.gg|discord\.com)/[^\s\"'<>]+", re.IGNORECASE),
}


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False
        self.meta_description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "a" and attr_map.get("href"):
            self.links.append(attr_map["href"])
        if tag.lower() == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if name in {"description", "og:description"} and attr_map.get("content"):
                self.meta_description = attr_map["content"]
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str | None:
        text = "".join(self.title_parts).strip()
        return text or None


def fetch_url(url: str, timeout: int = 15) -> tuple[str, dict[str, str]]:
    request = Request(
        url,
        headers={
            "User-Agent": "MarshallBot/0.1 (+https://example.invalid)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
        return body, {"content_type": content_type, "charset": charset}


def extract_links(html: str, base_url: str | None = None) -> dict[str, list[str] | str | None]:
    parser = _LinkCollector()
    parser.feed(html)
    links = parser.links
    if base_url:
        links = [urljoin(base_url, link) for link in links]

    social_links = {
        "telegram": [],
        "x": [],
        "discord": [],
    }
    for link in links:
        parsed = urlparse(link)
        host = parsed.netloc.lower()
        if "t.me" in host or "telegram.me" in host:
            social_links["telegram"].append(link)
        elif "x.com" in host or "twitter.com" in host:
            social_links["x"].append(link)
        elif "discord.gg" in host or "discord.com" in host:
            social_links["discord"].append(link)

    return {
        "title": parser.title,
        "meta_description": parser.meta_description,
        "links": links,
        "telegram_links": social_links["telegram"],
        "x_links": social_links["x"],
        "discord_links": social_links["discord"],
    }


def extract_social_links(text: str) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        results[platform] = sorted(set(pattern.findall(text)))
    return results


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

