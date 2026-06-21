from __future__ import annotations

import re
from html.parser import HTMLParser
from decimal import Decimal
from urllib.parse import urljoin

from app.services.connectors import fetch_text
from app.services.extractor import extract_links
from app.services.sources import DiscoverySource


COIN_URL_RE = re.compile(r"^/coin/([A-Za-z0-9]+)$")
MC_RE = re.compile(r"\$?\s*([\d,.]+)\s*([KMB])?\s*MC", re.IGNORECASE)
AGE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*([smhd])\b", re.IGNORECASE)


def _parse_market_cap(text: str) -> float | None:
    match = MC_RE.search(text)
    if not match:
        return None

    value = Decimal(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").upper()
    if suffix == "K":
        value *= Decimal("1000")
    elif suffix == "M":
        value *= Decimal("1000000")
    elif suffix == "B":
        value *= Decimal("1000000000")
    return float(value)


def _parse_age_minutes(text: str) -> float | None:
    matches = AGE_RE.findall(text or "")
    if not matches:
        return None

    for raw_value, unit in matches:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        unit = unit.lower()
        if unit == "s":
            return max(0.0, value / 60.0)
        if unit == "m":
            return max(0.0, value)
        if unit == "h":
            return max(0.0, value * 60.0)
        if unit == "d":
            return max(0.0, value * 1440.0)
    return None


class _PumpFunParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.projects: list[dict] = []
        self._current_href: str | None = None
        self._current_text_parts: list[str] = []
        self._capture = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): v for k, v in attrs if v is not None}
        href = attrs_map.get("href")
        if tag.lower() == "a" and href and COIN_URL_RE.match(href):
            self._current_href = href
            self._current_text_parts = []
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._current_text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._capture and self._current_href:
            text = " ".join(part.strip() for part in self._current_text_parts if part.strip())
            self.projects.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._current_text_parts = []
            self._capture = False


class PumpFunSource(DiscoverySource):
    def __init__(self, url: str = "https://pump.fun/") -> None:
        self.url = url

    def collect(self) -> list[dict]:
        html = fetch_text(self.url)
        parser = _PumpFunParser()
        parser.feed(html)

        projects: list[dict] = []
        for item in parser.projects:
            text = item["text"]
            href = item["href"]
            parts = text.split()
            canonical_name = parts[0].strip() if parts else href.rsplit("/", 1)[-1]
            market_cap = _parse_market_cap(text)
            age_minutes = _parse_age_minutes(text)
            projects.append(
                {
                    "canonical_name": canonical_name,
                    "chain": "solana",
                    "website_url": None,
                    "telegram_url": None,
                    "x_url": None,
                    "discord_url": None,
                    "launch_source": "pump-fun",
                    "source_type": "launchpad",
                    "source_name": "pump-fun",
                    "pumpfun_url": urljoin(self.url, href),
                    "market_cap_estimate": market_cap,
                    "project_age_minutes": age_minutes,
                    "raw_text": text,
                }
            )
        return sorted(
            projects,
            key=lambda item: (
                float(item.get("project_age_minutes") if item.get("project_age_minutes") is not None else 999999.0),
                float(item.get("market_cap_estimate") if item.get("market_cap_estimate") is not None else 999999999.0),
            ),
        )


def enrich_pumpfun_project(project: dict) -> dict:
    pumpfun_url = project.get("pumpfun_url")
    if not pumpfun_url:
        return dict(project)

    html = fetch_text(str(pumpfun_url))
    parsed = extract_links(html, base_url=str(pumpfun_url))
    links = parsed.get("links", [])
    website_links = [link for link in links if link and "pump.fun" not in link.lower() and "t.me" not in link.lower() and "twitter.com" not in link.lower() and "x.com" not in link.lower()]
    telegram_links = parsed.get("telegram_links", [])
    x_links = parsed.get("x_links", [])
    discord_links = parsed.get("discord_links", [])

    enriched = dict(project)
    if website_links and not enriched.get("website_url"):
        enriched["website_url"] = website_links[0]
    if telegram_links and not enriched.get("telegram_url"):
        enriched["telegram_url"] = telegram_links[0]
    if x_links and not enriched.get("x_url"):
        enriched["x_url"] = x_links[0]
    if discord_links and not enriched.get("discord_url"):
        enriched["discord_url"] = discord_links[0]
    enriched["pumpfun_snapshot"] = {
        "title": parsed.get("title"),
        "meta_description": parsed.get("meta_description"),
        "links": links,
        "website_links": website_links,
        "telegram_links": telegram_links,
        "x_links": x_links,
        "discord_links": discord_links,
    }
    return enriched
