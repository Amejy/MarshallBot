from __future__ import annotations

import asyncio
import html as html_module
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.connectors import fetch_text
from app.services.extractor import extract_links, extract_social_links
from app.services.sources import DiscoverySource

try:  # pragma: no cover - optional dependency
    from telethon import TelegramClient
except Exception:  # pragma: no cover - optional dependency
    TelegramClient = None  # type: ignore[assignment]


URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
TOKEN_NAME_RE = re.compile(r"^\s*[\$#]?([A-Z0-9]{2,24})\b")
PUBLIC_CHANNEL_RE = re.compile(r"^@?([A-Za-z0-9_]{5,32})$")
TELEGRAM_MESSAGE_TEXT_RE = re.compile(
    r'<div\b[^>]*class=(?:"[^"]*tgme_widget_message_text[^"]*"|\'[^\']*tgme_widget_message_text[^\']*\')[^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class TelegramResearchConfig:
    api_id: int = settings.telegram_api_id
    api_hash: str = settings.telegram_api_hash
    session_string: str = settings.telegram_session_string

    @property
    def ready(self) -> bool:
        return bool(self.api_id and self.api_hash and self.session_string)

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.api_id:
            missing.append("telegram_api_id")
        if not self.api_hash:
            missing.append("telegram_api_hash")
        if not self.session_string:
            missing.append("telegram_session_string")
        return missing

    def status(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "missing_fields": self.missing_fields,
            "api_id_set": bool(self.api_id),
            "api_hash_set": bool(self.api_hash),
            "session_string_set": bool(self.session_string),
        }


def _infer_project_name(text: str, fallback: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return fallback

    first = re.sub(r"^[^\w$#]+", "", lines[0]).strip()
    first = re.split(r"[|:•\-]", first, maxsplit=1)[0].strip()
    token_match = TOKEN_NAME_RE.match(first)
    if token_match:
        return token_match.group(1)
    if len(first) >= 2:
        return first[:80]
    return fallback


def _extract_website_links(text: str) -> list[str]:
    links = []
    for link in URL_RE.findall(text or ""):
        lowered = link.lower()
        if any(host in lowered for host in ("t.me/", "telegram.me/", "x.com/", "twitter.com/", "discord.gg/", "discord.com/")):
            continue
        links.append(link.rstrip(").,]}>"))
    return sorted(set(links))


def _clean_text_for_name(text: str) -> str:
    return URL_RE.sub(" ", text)


def normalize_public_channel_name(value: str) -> str | None:
    match = PUBLIC_CHANNEL_RE.match(str(value or "").strip())
    if not match:
        return None
    return match.group(1)


def normalize_public_channel_url(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        match = re.search(r"t\.me/(?:s/)?([A-Za-z0-9_]{5,32})", raw, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    return normalize_public_channel_name(raw)


def _strip_html(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_public_channel_messages(html: str) -> list[str]:
    return [match.strip() for match in TELEGRAM_MESSAGE_TEXT_RE.findall(html) if match.strip()]


def build_telegram_onboarding(channels: list[str], chain: str = "solana", name_prefix: str = "telegram-research") -> dict[str, object]:
    normalized_channels: list[str] = []
    invalid_channels: list[str] = []
    for channel in channels:
        normalized = normalize_public_channel_name(channel)
        if normalized:
            normalized_channels.append(normalized)
        else:
            invalid_channels.append(str(channel).strip())

    example_entry = {
        "name": name_prefix,
        "enabled": True,
        "mode": "research",
        "chain": chain,
        "limit": 100,
        "channels": normalized_channels,
    }
    return {
        "chain": chain,
        "requested": [str(channel).strip() for channel in channels if str(channel).strip()],
        "channels": normalized_channels,
        "invalid_channels": invalid_channels,
        "count": len(normalized_channels),
        "example": example_entry,
        "example_json": {
            "name": name_prefix,
            "enabled": True,
            "mode": "research",
            "chain": chain,
            "limit": 100,
            "channels": normalized_channels,
        },
    }


class TelegramResearchSource(DiscoverySource):
    def __init__(
        self,
        name: str,
        channels: list[str],
        chain: str = "solana",
        limit: int = 100,
        config: TelegramResearchConfig | None = None,
    ) -> None:
        self.name = name
        self.channels = channels
        self.chain = chain
        self.limit = limit
        self.config = config or TelegramResearchConfig()

    async def _collect_async(self) -> list[dict]:
        if TelegramClient is None or not self.config.ready:
            return []

        collected: list[dict] = []
        async with TelegramClient(
            self.config.session_string,
            self.config.api_id,
            self.config.api_hash,
        ) as client:
            for channel in self.channels:
                async for message in client.iter_messages(channel, limit=self.limit):
                    text = (message.message or "").strip()
                    if not text:
                        continue
                    website_links = _extract_website_links(text)
                    social_links = extract_social_links(text)
                    telegram_links = social_links.get("telegram", [])
                    if not website_links or not telegram_links:
                        continue

                    collected.append(
                        {
                            "canonical_name": _infer_project_name(_clean_text_for_name(text), fallback=str(channel)),
                            "chain": self.chain,
                            "website_url": website_links[0] if website_links else None,
                            "telegram_url": telegram_links[0] if telegram_links else None,
                            "x_url": social_links.get("x", [None])[0],
                            "discord_url": social_links.get("discord", [None])[0],
                            "launch_source": self.name,
                            "source_type": "telegram",
                            "source_name": self.name,
                            "telegram_channel": channel,
                            "telegram_message_id": getattr(message, "id", None),
                            "telegram_message_date": getattr(message, "date", None),
                            "raw_text": text,
                        }
                    )
        return collected

    def collect(self) -> list[dict]:
        if not self.config.ready or TelegramClient is None:
            return []
        return asyncio.run(self._collect_async())


class TelegramPublicChannelSource(DiscoverySource):
    def __init__(self, name: str, channel: str, chain: str = "solana", limit: int = 20) -> None:
        self.name = name
        self.channel = normalize_public_channel_url(channel) or str(channel).strip().lstrip("@")
        self.chain = chain
        self.limit = limit

    def collect(self) -> list[dict]:
        if not self.channel:
            return []

        page_url = f"https://t.me/s/{self.channel}"
        try:
            html = fetch_text(page_url)
        except Exception:
            return []

        items: list[dict] = []
        for block in _extract_public_channel_messages(html)[: self.limit]:
            parsed = extract_links(block, base_url=page_url)
            text_source = re.sub(r"<a\b[^>]*>.*?</a>", " ", block, flags=re.IGNORECASE | re.DOTALL)
            raw_text = _strip_html(text_source)
            website_links = _extract_website_links(raw_text)
            socials = extract_social_links(raw_text)
            website_links.extend(
                [
                    link
                    for link in parsed.get("links", [])
                    if link
                    and not any(
                        host in link.lower()
                        for host in ("t.me/", "telegram.me/", "x.com/", "twitter.com/", "discord.gg/", "discord.com/")
                    )
                ]
            )
            website_links = list(dict.fromkeys(website_links))
            telegram_links = list(dict.fromkeys([*(parsed.get("telegram_links") or []), *socials.get("telegram", [])]))
            x_links = list(dict.fromkeys([*(parsed.get("x_links") or []), *socials.get("x", [])]))
            discord_links = list(dict.fromkeys([*(parsed.get("discord_links") or []), *socials.get("discord", [])]))
            if not website_links or not telegram_links:
                continue

            items.append(
                {
                    "canonical_name": _infer_project_name(_clean_text_for_name(raw_text), fallback=self.channel),
                    "chain": self.chain,
                    "website_url": website_links[0],
                    "telegram_url": telegram_links[0],
                    "x_url": x_links[0] if x_links else None,
                    "discord_url": discord_links[0] if discord_links else None,
                    "launch_source": self.name,
                    "source_type": "telegram",
                    "source_name": self.name,
                    "telegram_channel": self.channel,
                    "telegram_channel_url": page_url,
                    "raw_text": raw_text,
                }
            )
        return items
