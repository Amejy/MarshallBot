from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings


@dataclass(slots=True)
class SourceConfig:
    launchpads: list[dict] = field(default_factory=list)
    telegram_channels: list[dict] = field(default_factory=list)
    social_accounts: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    blacklisted_domains: list[str] = field(default_factory=list)
    blacklisted_telegram: list[str] = field(default_factory=list)
    trusted_sources: list[str] = field(default_factory=list)

    @staticmethod
    def _merge_named_sources(existing: list[dict], enabled_names: list[str], presets: dict[str, dict]) -> list[dict]:
        if not enabled_names:
            return existing

        existing_by_name = {
            str(item.get("name", "")).strip().lower(): item
            for item in existing
            if str(item.get("name", "")).strip()
        }
        merged: list[dict] = []
        seen: set[str] = set()
        for name in enabled_names:
            normalized_name = str(name).strip().lower()
            if not normalized_name or normalized_name in seen:
                continue
            seen.add(normalized_name)
            if normalized_name in existing_by_name:
                merged.append(existing_by_name[normalized_name])
                continue
            preset = presets.get(normalized_name)
            if preset:
                merged.append(dict(preset))
        return merged

    @staticmethod
    def _selection_summary(enabled_names: list[str], selected_sources: list[dict], presets: dict[str, dict]) -> dict[str, object]:
        enabled_lookup = [str(name).strip() for name in enabled_names if str(name).strip()]
        active_names = [str(item.get("name", "")).strip() for item in selected_sources if str(item.get("name", "")).strip()]
        selected_lookup = {name.lower() for name in active_names}
        unknown_names = [name for name in enabled_lookup if name.lower() not in presets and name.lower() not in selected_lookup]
        return {
            "requested": enabled_lookup,
            "active": active_names,
            "count": len(active_names),
            "unknown": unknown_names,
        }

    @classmethod
    def load(cls, path: str | Path = "config/sources.json") -> "SourceConfig":
        config_path = Path(path)
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}

        launchpad_presets = {
            "pump-fun": {
                "name": "pump-fun",
                "chain": "solana",
                "enabled": True,
                "mode": "pumpfun",
                "url": "https://pump.fun/",
            },
            "four-meme": {
                "name": "four-meme",
                "chain": "bsc",
                "enabled": True,
                "mode": "fourmeme",
                "url": "https://four.meme",
                "limit": 50,
            },
            "solana-homepages": {
                "name": "solana-homepages",
                "chain": "solana",
                "enabled": True,
                "mode": "sitemap",
                "url": "https://example.com",
                "limit": 25,
            },
            "bsc-homepages": {
                "name": "bsc-homepages",
                "chain": "bsc",
                "enabled": True,
                "mode": "sitemap",
                "url": "https://example.com",
                "limit": 25,
            },
            "crypto-breaking-news": {
                "name": "crypto-breaking-news",
                "chain": "solana",
                "enabled": True,
                "mode": "rss",
                "url": "https://www.cryptobreaking.com/feed/",
            },
        }
        telegram_presets = {
            "alpha-meme-watch": {
                "name": "alpha-meme-watch",
                "enabled": True,
                "mode": "research",
                "chain": "solana",
                "limit": 100,
                "channels": ["AlphaMemeWatch"],
            },
            "telegram-research-template": {
                "name": "telegram-research-template",
                "enabled": True,
                "mode": "research",
                "chain": "solana",
                "limit": 100,
                "channels": ["YOUR_PUBLIC_CHANNEL_USERNAME"],
            },
        }
        social_presets = {
            "alpha-x-watch": {
                "name": "alpha-x-watch",
                "enabled": True,
                "mode": "rss",
                "chain": "solana",
                "limit": 25,
                "url": "https://example.com/feed.xml",
            },
            "bsc-social-feed": {
                "name": "bsc-social-feed",
                "enabled": True,
                "mode": "rss",
                "chain": "bsc",
                "limit": 25,
                "url": "https://example.com/bsc-feed.xml",
            },
            "pumpfun-x-watch": {
                "name": "pumpfun-x-watch",
                "enabled": True,
                "mode": "profile",
                "chain": "solana",
                "limit": 25,
                "url": "https://x.com/pumpdotfun",
            },
            "dexscreener-x-watch": {
                "name": "dexscreener-x-watch",
                "enabled": True,
                "mode": "profile",
                "chain": "multi",
                "limit": 25,
                "url": "https://x.com/dexscreener",
            },
            "dexscreener-solana-watch": {
                "name": "dexscreener-solana-watch",
                "enabled": True,
                "mode": "profile",
                "chain": "solana",
                "limit": 25,
                "url": "https://dexscreener.com/solana",
            },
            "dexscreener-bsc-watch": {
                "name": "dexscreener-bsc-watch",
                "enabled": True,
                "mode": "profile",
                "chain": "bsc",
                "limit": 25,
                "url": "https://dexscreener.com/bsc",
            },
        }

        launchpads = list(data.get("launchpads", []))
        telegram_channels = list(data.get("telegram_channels", []))
        social_accounts = list(data.get("social_accounts", []))
        launchpads = cls._merge_named_sources(launchpads, list(settings.launchpad_sources), launchpad_presets)
        telegram_channels = cls._merge_named_sources(telegram_channels, list(settings.telegram_channels), telegram_presets)
        social_accounts = cls._merge_named_sources(social_accounts, list(settings.social_accounts), social_presets)

        return cls(
            launchpads=launchpads,
            telegram_channels=telegram_channels,
            social_accounts=social_accounts,
            keywords=list(data.get("keywords", [])),
            blacklisted_domains=list(data.get("blacklisted_domains", [])),
            blacklisted_telegram=list(data.get("blacklisted_telegram", [])),
            trusted_sources=list(data.get("trusted_sources", [])),
        )


def build_source_selection_summary(config: SourceConfig | None = None) -> dict[str, object]:
    config = config or SourceConfig.load()
    return {
        "launchpads": SourceConfig._selection_summary(list(settings.launchpad_sources), config.launchpads, {
            "pump-fun": {"name": "pump-fun"},
            "four-meme": {"name": "four-meme"},
            "solana-homepages": {"name": "solana-homepages"},
            "bsc-homepages": {"name": "bsc-homepages"},
            "crypto-breaking-news": {"name": "crypto-breaking-news"},
        }),
            "telegram_channels": SourceConfig._selection_summary(list(settings.telegram_channels), config.telegram_channels, {
            "alpha-meme-watch": {"name": "alpha-meme-watch"},
            "telegram-research-template": {"name": "telegram-research-template"},
        }),
        "social_accounts": SourceConfig._selection_summary(list(settings.social_accounts), config.social_accounts, {
            "alpha-x-watch": {"name": "alpha-x-watch"},
            "bsc-social-feed": {"name": "bsc-social-feed"},
            "pumpfun-x-watch": {"name": "pumpfun-x-watch"},
            "dexscreener-x-watch": {"name": "dexscreener-x-watch"},
            "dexscreener-solana-watch": {"name": "dexscreener-solana-watch"},
            "dexscreener-bsc-watch": {"name": "dexscreener-bsc-watch"},
        }),
        "keywords": list(config.keywords),
        "blacklisted_domains": list(config.blacklisted_domains),
        "blacklisted_telegram": list(config.blacklisted_telegram),
        "trusted_sources": list(config.trusted_sources),
    }


def build_source_coverage_summary(config: SourceConfig | None = None, templates_count: int = 0) -> dict[str, object]:
    config = config or SourceConfig.load()
    selection = build_source_selection_summary(config)
    active_launchpads = selection["launchpads"]["count"]
    active_telegram = selection["telegram_channels"]["count"]
    active_social = selection["social_accounts"]["count"]
    active_sources = active_launchpads + active_telegram + active_social
    unknown_sources = len(selection["launchpads"]["unknown"]) + len(selection["telegram_channels"]["unknown"])
    ready = active_sources > 0 and unknown_sources == 0
    return {
        "ready": ready,
        "active_sources": active_sources,
        "active_launchpads": active_launchpads,
        "active_telegram_channels": active_telegram,
        "active_social_accounts": active_social,
        "source_templates": templates_count,
        "keywords": len(selection["keywords"]),
        "trusted_sources": len(selection["trusted_sources"]),
        "unknown_sources": unknown_sources,
    }
