from __future__ import annotations

from app.core.source_config import SourceConfig
from app.services.connectors import AtomFeedSource, HTMLListingSource, JSONFeedSource, PublicProfileSource, RSSFeedSource, SitemapSource
from app.services.launchpad_sources import FourMemeSource
from app.services.pumpfun import PumpFunSource
from app.services.telegram_research import TelegramPublicChannelSource, TelegramResearchSource
from app.services.source_adapters import LaunchpadSource, TelegramAnnouncementSource
from app.services.sources import CompositeDiscoverySource, StaticDiscoverySource


class _TaggedSource:
    def __init__(self, source, source_name: str, source_type: str) -> None:
        self.source = source
        self.source_name = source_name
        self.source_type = source_type

    def collect(self) -> list[dict]:
        items: list[dict] = []
        for item in self.source.collect():
            items.append(
                dict(
                    item,
                    launch_source=item.get("launch_source", self.source_name),
                    source_type=self.source_type,
                    source_name=item.get("source_name", self.source_name),
                )
            )
        return items


def _build_url_based_source(name: str, chain: str, mode: str, url: str, limit: int, source_type: str) -> object:
    if mode == "json":
        return _TaggedSource(JSONFeedSource(name, url, chain=chain, items_path="items"), name, source_type)
    if mode == "rss":
        return _TaggedSource(RSSFeedSource(name, url, chain=chain), name, source_type)
    if mode == "atom":
        return _TaggedSource(AtomFeedSource(name, url, chain=chain), name, source_type)
    if mode == "html":
        return _TaggedSource(HTMLListingSource(name, url, chain=chain), name, source_type)
    if mode == "profile":
        return _TaggedSource(PublicProfileSource(name, url, chain=chain), name, source_type)
    if mode == "sitemap":
        return _TaggedSource(SitemapSource(name, url, chain=chain, max_pages=limit), name, source_type)
    return None


def build_source_registry(config: SourceConfig) -> dict[str, object]:
    registry: dict[str, object] = {}

    for launchpad in config.launchpads:
        if not launchpad.get("enabled", True):
            continue
        name = launchpad["name"]
        chain = launchpad.get("chain", "solana")
        mode = launchpad.get("mode", "sample")
        if mode == "pumpfun":
            registry[name] = PumpFunSource(url=str(launchpad.get("url") or "https://pump.fun/"))
        elif mode == "fourmeme":
            registry[name] = FourMemeSource(
                url=str(launchpad.get("url") or "https://four.meme"),
                limit=int(launchpad.get("limit", 50)),
            )
        elif mode == "json" and launchpad.get("url"):
            registry[name] = JSONFeedSource(
                name,
                str(launchpad["url"]),
                chain=chain,
                items_path=str(launchpad.get("items_path", "items")),
            )
        elif mode == "rss" and launchpad.get("url"):
            registry[name] = RSSFeedSource(name, str(launchpad["url"]), chain=chain)
        elif mode == "atom" and launchpad.get("url"):
            registry[name] = AtomFeedSource(name, str(launchpad["url"]), chain=chain)
        elif mode == "html" and launchpad.get("url"):
            registry[name] = HTMLListingSource(name, str(launchpad["url"]), chain=chain)
        elif mode == "sitemap" and launchpad.get("url"):
            registry[name] = SitemapSource(
                name,
                str(launchpad["url"]),
                chain=chain,
                max_pages=int(launchpad.get("limit", 25)),
            )
        else:
            registry[name] = LaunchpadSource(
                name,
                [
                    {
                        "canonical_name": f"{name}-sample",
                        "chain": chain,
                        "website_url": "https://example.com",
                        "telegram_url": "https://t.me/example",
                        "trusted_sources": config.trusted_sources,
                    }
                ],
                chain=chain,
            )

    for channel in config.telegram_channels:
        if not channel.get("enabled", True):
            continue
        name = channel["name"]
        mode = channel.get("mode", "sample")
        if mode in {"research", "telethon"}:
            research_channels = channel.get("channels") or channel.get("usernames") or [name]
            registry[name] = TelegramResearchSource(
                name,
                [str(item) for item in research_channels if str(item).strip()],
                chain=channel.get("chain", "solana"),
                limit=int(channel.get("limit", 100)),
            )
        elif mode in {"public", "web"}:
            public_channel = channel.get("channel") or (channel.get("channels") or channel.get("usernames") or [name])[0]
            registry[name] = TelegramPublicChannelSource(
                name,
                str(public_channel),
                chain=channel.get("chain", "solana"),
                limit=int(channel.get("limit", 20)),
            )
        else:
            registry[name] = TelegramAnnouncementSource(
                name,
                [
                    {
                        "canonical_name": f"{name}-sample",
                        "chain": "solana",
                        "website_url": "https://example.com",
                        "telegram_url": "https://t.me/example",
                        "trusted_sources": config.trusted_sources,
                    }
                ],
            )

    for account in config.social_accounts:
        if not account.get("enabled", True):
            continue
        name = str(account.get("name", "")).strip()
        if not name:
            continue
        chain = str(account.get("chain", "solana"))
        mode = str(account.get("mode", "sample"))
        url = str(account.get("url", "")).strip()
        limit = int(account.get("limit", 25))
        items = account.get("items") or account.get("posts") or []
        if items:
            registry[name] = _TaggedSource(
                LaunchpadSource(name, list(items), chain=chain),
                name,
                "social",
            )
            continue
        url_based_source = _build_url_based_source(name, chain, mode, url, limit, "social") if url else None
        if url_based_source is not None:
            registry[name] = url_based_source
        else:
            registry[name] = _TaggedSource(
                StaticDiscoverySource(
                    [
                        {
                            "canonical_name": f"{name}-sample",
                            "chain": chain,
                            "website_url": "https://example.com",
                            "telegram_url": "https://t.me/example",
                            "trusted_sources": config.trusted_sources,
                        }
                    ]
                ),
                name,
                "social",
            )

    if not registry:
        registry["sample"] = StaticDiscoverySource(
            [
                {
                    "canonical_name": "Sample Project",
                    "chain": "solana",
                    "website_url": "https://example.com",
                    "telegram_url": "https://t.me/example",
                    "launch_source": "sample",
                    "source_type": "demo",
                    "source_name": "sample",
                }
            ]
        )

    return registry


def build_composite_source(config: SourceConfig) -> CompositeDiscoverySource:
    registry = build_source_registry(config)
    return CompositeDiscoverySource(list(registry.values()))
