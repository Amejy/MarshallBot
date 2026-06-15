from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.extractor import extract_social_links
from app.services.sources import DiscoverySource

try:  # pragma: no cover - optional dependency
    from telethon import TelegramClient
except Exception:  # pragma: no cover - optional dependency
    TelegramClient = None  # type: ignore[assignment]


URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
TOKEN_NAME_RE = re.compile(r"^\s*[\$#]?([A-Z0-9]{2,24})\b")
PUBLIC_CHANNEL_RE = re.compile(r"^@?([A-Za-z0-9_]{5,32})$")


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


def normalize_public_channel_name(value: str) -> str | None:
    match = PUBLIC_CHANNEL_RE.match(str(value or "").strip())
    if not match:
        return None
    return match.group(1)


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
                    if not website_links and not telegram_links:
                        continue

                    collected.append(
                        {
                            "canonical_name": _infer_project_name(text, fallback=str(channel)),
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
