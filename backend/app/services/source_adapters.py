from __future__ import annotations

from app.services.launchpad_adapters import StaticLaunchpadAdapter
from app.services.sources import DiscoverySource


class LaunchpadSource(StaticLaunchpadAdapter):
    def __init__(self, name: str, items: list[dict], chain: str = "solana") -> None:
        super().__init__(name, chain, items)


class TelegramAnnouncementSource(DiscoverySource):
    def __init__(self, channel_name: str, items: list[dict]) -> None:
        self.channel_name = channel_name
        self.items = items

    def collect(self) -> list[dict]:
        return [dict(item, launch_source=self.channel_name, source_type="telegram", source_name=self.channel_name) for item in self.items]
